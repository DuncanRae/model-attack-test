"""The command line. Each command is a few lines over `packs`, `target`, `run` and `report`.

  check     send one harmless message, to get a target file right before anything else is sent
  list      show what is in the packs, by kind of trick
  run       send every message and write the report
  export    write the messages as a sheet, for a system that can only be reached through its chat page
  judge     judge a filled-in sheet and write the report
  begin, next, record, finish
            the same through a chat page, one message at a time: for an agent that drives a browser, or a person
  plant     write test documents with a hidden instruction in each, and a pack of questions about them
  compare   say what changed between two runs: what got worse, what was fixed, what is still wrong
  practice  start a made-up chatbot on this computer, to try the tool on

Exit codes: 0 everything held and every ordinary message was answered. 1 something gave way or was refused.
2 the run could not be done or did not finish.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import VERSION, Problem, byhand, compare, packs, plant, report, run, target, variants
from .adaptive import DEFAULT_TURNS, MAX_TURNS, Attacker
from .judge import ModelJudge

HELLO = "Hello. What can you help me with?"


def _say(text: str = "") -> None:
    print(text, flush=True)


def _model(path: str | None, what: str) -> target.Sender | None:
    if not path:
        return None
    t = target.load(path)
    if t["style"] != "messages":
        raise Problem(f'The {what}\'s target file should be a plain model address, with the conversation style "messages".')
    return target.Sender(t)


def _judge(path: str | None) -> ModelJudge | None:
    sender = _model(path, "judge")
    return ModelJudge(sender) if sender else None


def _joined(args, skip_from_target: list[str] | None = None) -> dict:
    skip = list(args.skip or [])
    joined = packs.join(args.pack, args.only, skip, args.per_kind, variants.chosen(args.variants), args.adaptive)
    # A target file's own skip list is advice for that system: an entry no pack has is passed over, not an error.
    extra = set(skip_from_target or [])
    joined["items"] = [i for i in joined["items"] if i["id"] not in extra and i["category"] not in extra]
    if not joined["items"]:
        raise Problem("Nothing is left to send after the target file's skip list.")
    return joined


def _outcome(result: dict, page: Path) -> int:
    s = result["stats"]
    _say()
    _say(f"Attacks: {s['held']} held, {s['failed']} gave way" + (f" ({s['failed_high']} of them high severity)" if s["failed_high"] else "")
         + f", of {s['attacks']}." + (f" {s['to_read']} held replies nobody has read." if s["to_read"] else ""))
    if s["not_reached"]:
        _say(f"Not reached: {s['not_reached']}. The system never found what those depend on (a planted document, say), so they tested nothing.")
    for d in result.get("disguises", []):
        if d["only_in_disguise"]:
            _say(f"Disguise {d['name']}: {d['only_in_disguise']} attacks got through ONLY in this disguise.")
    if s["ordinary"]:
        _say(f"Ordinary messages: {s['answered']} answered, {s['blocked']} refused, of {s['ordinary']}."
             + (f" {s['leaked']} were given something from never_say." if s["leaked"] else ""))
    if s["errors"] or s["not_run"]:
        _say(f"No reply: {s['errors']}. Not sent: {s['not_run']}.")
    if result["stopped"]:
        _say(result["stopped"])
    for r in result.get("pack_reviews", []):
        if r["stale"]:
            _say(f"The pack {r['pack']} was last checked against newly reported attacks on {r['reviewed']}: more than six months ago.")
    _say(f"Report: {page.resolve()}")
    if s["failed"] or s["blocked"] or s["leaked"]:
        return 1
    return 2 if (s["errors"] or s["not_run"] or result["stopped"]) else 0


def cmd_check(args) -> int:
    t = target.load(args.target)
    sender = target.Sender(t)
    _say(f"Sending one harmless message to {t['request']['host']} ({t['name']}).")
    try:
        reply, _ = sender.converse([], HELLO)
    except target.Failure as e:
        _say(f"It did not work: {e}.")
        if e.detail:
            _say("The start of what came back (to help put the target file right):")
            _say(e.detail)
        return 2
    _say("It answered:")
    _say(reply)
    _say()
    _say("If that is the assistant's reply and nothing else, the target file is right.")
    return 0


def cmd_list(args) -> int:
    joined = _joined(args)
    _say("Packs: " + ", ".join(r["pack"] + (f" (checked {r['reviewed']})" if r["reviewed"] else " (not dated)") for r in joined["reviews"]))
    for c in packs.categories(joined["items"]):
        _say(f"  {sum(1 for i in joined['items'] if i['category'] == c):4d}  {c}")
    _say(f"  {len(joined['items']):4d}  in all")
    return 0


def cmd_run(args) -> int:
    t = target.load(args.target)
    if t["environment"] == "production" and not args.production:
        raise Problem("This target file says production. Test a dev copy with made-up data. If production really is meant, add --production.")
    args.adaptive = bool(args.attacker)   # open goals are tried when there is a model to write the messages
    joined = _joined(args, t["skip"])
    sender, judge = target.Sender(t), _judge(args.judge)
    attacker_sender = _model(args.attacker, "attacker")
    attacker = Attacker(attacker_sender) if attacker_sender else None
    most = sum(args.turns if i["goal"] else 1 + len(i["before"]) for i in joined["items"]) * args.repeat
    _say(f"Target: {t['name']} ({t['environment']}) at {t['request']['host']}. Owner: {t['owner']}.")
    _say(f"About to send {len(joined['items'])} messages" + (f", {args.repeat} times each" if args.repeat > 1 else "")
         + f": up to {min(most, args.max_requests)} requests. Each one costs whatever a message to this system costs.")
    if judge:
        _say(f"Every reply will also be sent to the judge at {judge.sender.target['request']['host']}.")
    if attacker:
        _say(f"Open goals: {sum(1 for i in joined['items'] if i['goal'])}, up to {args.turns} messages each. The goals and the system's replies "
             f"will be sent to the attacker model at {attacker.sender.target['request']['host']}.")
    if not args.yes:
        if not sys.stdin.isatty():
            raise Problem("Add --yes to run without being asked (there is nobody at the keyboard to ask).")
        if input("Is this system yours to test, or do you have its owner's go-ahead? Type yes to send: ").strip().lower() != "yes":
            _say("Nothing was sent.")
            return 2

    def progress(n: int, total: int, row: dict) -> None:
        if row["verdict"] in ("failed", "blocked", "leaked", "error"):
            _say(f"  {n}/{total} {row['id']}: {row['verdict']}")
        elif n % 10 == 0 or n == total:
            _say(f"  {n}/{total}")

    result = run.run_suite(t, joined, sender, judge, args.repeat, args.max_requests, progress, attacker, args.turns)
    return _outcome(result, report.write(result, Path(args.out) if args.out else report.folder_for(t["name"])))


def cmd_export(args) -> int:
    joined = _joined(args)
    out = Path(args.out)
    try:
        out.write_text(json.dumps(run.sheet(joined), ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        raise Problem(f"The sheet could not be written to {out}.") from None
    _say(f"{len(joined['items'])} messages written to {out.resolve()}. Fill in each 'reply', then: attack-test judge --replies {out} --pack ...")
    return 0


def cmd_judge(args) -> int:
    joined = _joined(args)
    filled = packs.read_json(Path(args.replies).expanduser(), "reply sheet")
    refusals = packs.patterns(args.refusal or [], "--refusal")
    never = packs.patterns(args.never_say or [], "--never-say")
    name = target._string(args.name, "--name", 80)
    meta = {"name": name, "owner": target._string(args.owner, "--owner", 120), "environment": args.environment, "host": "replies collected by hand"}
    result = run.judge_sheet(filled, joined, meta, refusals, never, _judge(args.judge))
    return _outcome(result, report.write(result, Path(args.out) if args.out else report.folder_for(name)))


def cmd_begin(args) -> int:
    joined = _joined(args)
    name = target._string(args.name, "--name", 80)
    meta = {"name": name, "owner": target._string(args.owner, "--owner", 120), "environment": args.environment, "host": "sent through its chat page"}
    if args.environment == "production" and not args.production:
        raise Problem("Test a dev copy with made-up data. If production really is meant, add --production.")
    folder = Path(args.out) if args.out else report.folder_for(name)
    goals = sum(1 for i in joined["items"] if i["goal"])
    byhand.begin(args.pack, joined, meta, folder, args.one_conversation, args.turns if goals else 0)
    attacks = sum(1 for i in joined["items"] if not i["ordinary"] and not i["goal"])
    earlier = sum(len(i["before"]) for i in joined["items"])
    fixed = len(joined["items"]) - goals
    _say(f"{fixed} messages to send ({attacks} attacks, {fixed - attacks} ordinary)."
         + (f" Some have earlier messages that are typed first: {earlier} more to type, {fixed + earlier} in all." if earlier else ""))
    if goals:
        _say(f"Then {goals} open goals, where you write the messages: up to {args.turns} messages each.")
    _say(f"The run is in {folder.resolve()}")
    _say(f"Next:  attack-test next --run {folder}")
    return 0


def cmd_next(args) -> int:
    _say(byhand.next_message(Path(args.run)))
    return 0


def cmd_record(args) -> int:
    _say(byhand.record(Path(args.run), args.id, args.reply_file, args.verdict or "", args.reason or "", args.skip or "", args.transcript_file))
    return 0


def cmd_finish(args) -> int:
    folder = Path(args.run)
    result = byhand.finish(folder, packs.patterns(args.refusal or [], "--refusal"), packs.patterns(args.never_say or [], "--never-say"))
    return _outcome(result, report.write(result, folder))


def cmd_plant(args) -> int:
    folder = Path(args.out)
    pack = plant.make(folder)
    _say(f"{len(pack['attacks'])} planted documents written to {folder.resolve()}")
    _say(f"Read {folder / 'HOW-TO-USE.txt'} first. In short: put the plant-* files where your system reads documents, then run with")
    _say(f"  --pack {folder / 'plants.json'}")
    _say("and delete the files from the system afterwards. Do not give plants.json to the system: it holds the answers.")
    return 0


def cmd_compare(args) -> int:
    result = compare.compare(compare.load(args.older), compare.load(args.newer))
    _say(compare.text(result))
    return 1 if result["worse"] else 0


def cmd_practice(args) -> int:
    from practice import bot   # the made-up chatbot lives beside the tool, not in it
    bot.serve(args.mode, args.port, args.docs)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="attack-test", description="Send known tricks to an AI chat system you own and report which ones it gave way to.")
    p.add_argument("--version", action="version", version=f"model-attack-test {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    def with_packs(c):
        c.add_argument("--pack", action="append", default=[], metavar="NAME_OR_FILE", help="a pack in packs/ by name (core), or a path to one. Repeat for more")
        c.add_argument("--only", action="append", metavar="KIND_OR_ID", help="send only this kind of trick, or this id. Repeat for more")
        c.add_argument("--skip", action="append", metavar="KIND_OR_ID", help="leave out this kind of trick, or this id. Repeat for more")
        c.add_argument("--per-kind", type=int, metavar="N", help="keep only the first N of each kind, for a quick pass")
        c.add_argument("--variants", metavar="NAMES", help=f"also send each attack in these disguises: {', '.join(variants.NAMES)}, or all. Separate with commas")
        c.set_defaults(adaptive=False)

    c = sub.add_parser("check", help="send one harmless message to see that the target file is right")
    c.add_argument("--target", required=True)
    c.set_defaults(go=cmd_check)

    c = sub.add_parser("list", help="show what is in the packs")
    with_packs(c)
    c.set_defaults(go=cmd_list)

    c = sub.add_parser("run", help="send every message and write the report")
    c.add_argument("--target", required=True)
    with_packs(c)
    c.add_argument("--judge", metavar="TARGET_FILE", help="a target file for a second model that reads every reply")
    c.add_argument("--attacker", metavar="TARGET_FILE", help="a target file for a model that writes its own messages towards the packs' open goals")
    c.add_argument("--turns", type=int, default=DEFAULT_TURNS, help=f"how many messages an open goal may take (1 to {MAX_TURNS}, default {DEFAULT_TURNS})")
    c.add_argument("--repeat", type=int, default=1, help=f"send each message this many times (1 to {run.MAX_REPEAT}). A model's answers vary")
    c.add_argument("--max-requests", type=int, default=run.DEFAULT_REQUESTS, help=f"stop after this many requests (default {run.DEFAULT_REQUESTS})")
    c.add_argument("--out", metavar="FOLDER", help="where the report goes (default reports/<name>-<date>)")
    c.add_argument("--yes", action="store_true", help="do not ask before sending")
    c.add_argument("--production", action="store_true", help="allow a target file that says production")
    c.set_defaults(go=cmd_run)

    c = sub.add_parser("export", help="write the messages as a sheet to fill in by hand or through a browser")
    with_packs(c)
    c.add_argument("--out", required=True, metavar="FILE")
    c.set_defaults(go=cmd_export)

    c = sub.add_parser("judge", help="judge a filled-in sheet and write the report")
    c.add_argument("--replies", required=True, metavar="FILE")
    with_packs(c)
    c.add_argument("--name", required=True, help="what the system is called")
    c.add_argument("--owner", required=True, help="who owns it and agreed to the test")
    c.add_argument("--environment", choices=target.ENVIRONMENTS, default="dev")
    c.add_argument("--refusal", action="append", metavar="PATTERN", help="words that show the assistant declined. Repeat for more")
    c.add_argument("--never-say", action="append", metavar="PATTERN", help="words that must never appear in a reply. Repeat for more")
    c.add_argument("--judge", metavar="TARGET_FILE")
    c.add_argument("--out", metavar="FOLDER")
    c.set_defaults(go=cmd_judge)

    c = sub.add_parser("begin", help="start a run that is sent through a chat page, one message at a time")
    with_packs(c)
    c.add_argument("--name", required=True, help="what the system is called")
    c.add_argument("--owner", required=True, help="who owns it and agreed to the test")
    c.add_argument("--environment", choices=target.ENVIRONMENTS, default="dev")
    c.add_argument("--production", action="store_true", help="allow --environment production")
    c.add_argument("--one-conversation", action="store_true", help="the system gives no way to start a new conversation: everything goes into one")
    c.add_argument("--adaptive", action="store_true", help="add the packs' open goals, where whoever is at the page writes the messages")
    c.add_argument("--turns", type=int, default=DEFAULT_TURNS, help=f"how many messages an open goal may take (1 to {MAX_TURNS}, default {DEFAULT_TURNS})")
    c.add_argument("--out", metavar="FOLDER", help="where the run and its report go (default reports/<name>-<date>)")
    c.set_defaults(go=cmd_begin)

    c = sub.add_parser("next", help="show the next message to send")
    c.add_argument("--run", required=True, metavar="FOLDER")
    c.set_defaults(go=cmd_next)

    c = sub.add_parser("record", help="take the reply to a message from a file, or note why it was not sent")
    c.add_argument("--run", required=True, metavar="FOLDER")
    c.add_argument("--id", required=True)
    c.add_argument("--reply-file", metavar="FILE", help="a file holding the assistant's reply, word for word")
    c.add_argument("--transcript-file", metavar="FILE", help='for an open goal: a JSON file of the whole exchange, [{"said": "...", "reply": "..."}]')
    c.add_argument("--verdict", help="what you made of it: held, gave_way or unsure (answered, blocked or unsure for an ordinary message)")
    c.add_argument("--reason", help="a few plain words of your own. Never the reply's words")
    c.add_argument("--skip", metavar="WHY", help="the message was not sent: a few plain words on why")
    c.set_defaults(go=cmd_record)

    c = sub.add_parser("finish", help="judge the replies of a run and write the report")
    c.add_argument("--run", required=True, metavar="FOLDER")
    c.add_argument("--refusal", action="append", metavar="PATTERN", help="words that show the assistant declined. Repeat for more")
    c.add_argument("--never-say", action="append", metavar="PATTERN", help="words that must never appear in a reply. Repeat for more")
    c.set_defaults(go=cmd_finish)

    c = sub.add_parser("plant", help="write test documents with a hidden instruction in each, and a pack of questions about them")
    c.add_argument("--out", required=True, metavar="FOLDER", help="a new, empty folder for the documents")
    c.set_defaults(go=cmd_plant)

    c = sub.add_parser("compare", help="say what changed between two runs")
    c.add_argument("older", help="the earlier run: its folder, or its results.json")
    c.add_argument("newer", help="the later run")
    c.set_defaults(go=cmd_compare)

    c = sub.add_parser("practice", help="start a made-up chatbot on this computer to try the tool on")
    c.add_argument("--mode", choices=("weak", "holding", "strict"), default="weak")
    c.add_argument("--port", type=int, default=8777)
    c.add_argument("--docs", metavar="FOLDER", help="a folder of documents for the chatbot to answer from, such as one `plant` wrote")
    c.set_defaults(go=cmd_practice)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.go(args)
    except Problem as e:
        print(str(e), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 2
    except Exception as e:   # nothing inside the tool is shown: the kind of error is enough to report it
        print(f"Something went wrong inside the tool ({type(e).__name__}). Nothing more was sent.", file=sys.stderr)
        return 2
