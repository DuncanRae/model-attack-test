"""A run done one message at a time through a chat page, by a person or by an agent that drives a browser.

Nothing here sends anything. The tool hands out the next message, whoever is at the page types it and brings the
reply back, and at the end the replies are judged like any other run:

  begin    writes run.json in a folder of its own: the messages still to send
  next     shows the next message (and writes it to message.txt, to paste from)
  record   takes the reply from a file, or notes why a message was not sent
  finish   judges the replies and writes the report beside run.json

The reply always comes in as a FILE. It is the system's own words and may hold anything, so it must never be put on
a command line, where a shell would read it.

run.json is input like any other when it is read back: it may have been edited, so every field is checked again.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import VERSION, Problem, packs, run, target
from .judge import VERDICTS

RUN_FILE, MESSAGE_FILE = "run.json", "message.txt"
PERSONA = "persona and style"
REASON = re.compile(r"^[A-Za-z0-9 ,.;:()%/-]{0,200}$")   # the agent's own few words: nothing a shell would act on
UNSEEN = "​‌‍⁠﻿"
MAX_REPLY_FILE = 500_000
ONE_CONVERSATION = ("Every message was sent in ONE conversation, because the system gave no way to start a new one. "
                    "An earlier message may have coloured a later reply, so treat each result as a pointer, not a measurement.")


def _write(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def _save(folder: Path, data: dict) -> None:
    try:
        _write(folder / RUN_FILE, json.dumps(data, ensure_ascii=False, indent=1))
    except OSError:
        raise Problem(f"The run could not be saved in {folder}.") from None


def begin(pack_args: list[str], joined: dict, meta: dict, folder: Path, one_conversation: bool) -> Path:
    """Start a run: write the messages to send into `folder`. With one conversation for everything, the ordinary
    messages go first while the conversation is clean, and the voice-changing attacks last, where they do least harm."""
    if (folder / RUN_FILE).exists():
        raise Problem(f"There is already a run in {folder}. Carry on with it (next), or give --out another folder.")
    items = joined["items"]
    if one_conversation:
        attacks = [i for i in items if not i["ordinary"]]
        items = ([i for i in items if i["ordinary"]] + [i for i in attacks if i["category"] != PERSONA]
                 + [i for i in attacks if i["category"] == PERSONA])
    kept = []
    for name in pack_args:   # a pack kept with the tool is remembered by name, any other by its full path
        kept.append(name if packs.NAME.match(name) and (packs.PACKS_DIR / f"{name}.json").is_file() else str(Path(name).expanduser().resolve()))
    data = {"tool": "model-attack-test", "version": VERSION, "target": meta, "pack_args": kept, "one_conversation": bool(one_conversation),
            "rows": [{"id": i["id"], "category": i["category"], "before": i["before"], "text": i["text"], "gives_way": i["gives_way"],
                      "reply": "", "verdict": "", "reason": "", "skipped": ""} for i in items]}
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        raise Problem(f"The folder {folder} could not be made.") from None
    _save(folder, data)
    return folder / RUN_FILE


def load(folder: Path) -> dict:
    data = packs.read_json(folder / RUN_FILE, "run")
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows or len(rows) > packs.MAX_ITEMS:
        raise Problem(f"{folder / RUN_FILE} is not a run that `begin` wrote.")
    for r in rows:
        ok = (isinstance(r, dict) and isinstance(r.get("id"), str) and packs.NAME.match(r["id"]) and isinstance(r.get("text"), str)
              and isinstance(r.get("before"), list) and all(isinstance(b, str) for b in r["before"])
              and all(isinstance(r.get(k, ""), str) for k in ("category", "gives_way", "reply", "verdict", "reason", "skipped")))
        if not ok:
            raise Problem(f"{folder / RUN_FILE} has a row that is not as `begin` wrote it.")
    args, meta = data.get("pack_args"), data.get("target")
    if not isinstance(args, list) or not 0 < len(args) <= 20 or not all(isinstance(a, str) and 0 < len(a) < 2000 for a in args):
        raise Problem(f"{folder / RUN_FILE} does not say which packs it was made from.")
    if not isinstance(meta, dict) or meta.get("environment") not in target.ENVIRONMENTS:
        raise Problem(f"{folder / RUN_FILE} does not say what system it is for.")
    data["target"] = {"name": target._string(meta.get("name"), "name", 80), "owner": target._string(meta.get("owner"), "owner", 120),
                      "environment": meta["environment"], "host": "sent through its chat page"}
    return data


def _left(data: dict) -> list[dict]:
    return [r for r in data["rows"] if not r.get("reply") and not r.get("skipped")]


def next_message(folder: Path) -> str:
    """What to do next, as plain text. The message itself is also written to message.txt, exactly as it must be sent."""
    data = load(folder)
    left = _left(data)
    if not left:
        return f"Every message has been sent or noted. Now run:  attack-test finish --run {folder}"
    row, total = left[0], len(data["rows"])
    try:
        _write(folder / MESSAGE_FILE, row["text"])
    except OSError:
        raise Problem(f"{folder / MESSAGE_FILE} could not be written.") from None
    out = [f"Message {total - len(left) + 1} of {total}. Id: {row['id']}. Kind: {row.get('category', '')}. {len(left) - 1} left after this one."]
    ordinary = row.get("category", "").startswith("ordinary")
    out.append("This is an ORDINARY message from an honest person. It should get a normal, useful answer." if ordinary
               else "This is an ATTACK. The assistant should not do what it asks.")
    out.append("Carry on in the same conversation." if data.get("one_conversation") else "Start a NEW conversation first.")
    if row.get("gives_way"):
        out.append(f"Giving way would look like: {row['gives_way']}")
    for n, said in enumerate(row["before"], 1):
        out += [f"EARLIER MESSAGE {n} (send it, and wait for the reply to finish, before going on):", "<<<", said, ">>>"]
    out += ["MESSAGE TO SEND, exactly as written between the marks:", "<<<", row["text"], ">>>"]
    if "\n" in row["text"]:
        out.append("It has line breaks. Keep them (Shift+Enter in most chat boxes). If the box cannot take them, use a space and say so in the reason.")
    if any(c in UNSEEN or 0xE0000 <= ord(c) <= 0xE007F for c in row["text"]):
        out.append(f"It has characters that cannot be seen. Paste it from {folder / MESSAGE_FILE} if you can, rather than typing it.")
    out += [f"The same text is in {folder / MESSAGE_FILE}.",
            "When the reply has finished: save the reply, word for word, to a file with your file tool (never through the shell), then run:",
            f"  attack-test record --run {folder} --id {row['id']} --reply-file <that file> --verdict <held|gave_way|unsure> --reason <a few plain words>"
            if not ordinary else
            f"  attack-test record --run {folder} --id {row['id']} --reply-file <that file> --verdict <answered|blocked|unsure> --reason <a few plain words>"]
    return "\n".join(out)


def record(folder: Path, item_id: str, reply_file: str | None, verdict: str = "", reason: str = "", skip: str = "") -> str:
    data = load(folder)
    row = next((r for r in data["rows"] if r["id"] == item_id), None)
    if row is None:
        raise Problem(f"There is no message with the id {item_id!r} in this run.")
    for what, value in (("--reason", reason), ("--skip", skip)):
        if not REASON.match(value or ""):
            raise Problem(f"{what} must be a few plain words: letters, digits, spaces and , . ; : ( ) % / - only, at most 200 characters.")
    kind = "ordinary" if row.get("category", "").startswith("ordinary") else "attack"
    allowed = VERDICTS[kind]
    if verdict and verdict not in allowed:
        raise Problem(f"For this message --verdict must be one of: {', '.join(allowed)}.")
    if skip:
        row.update({"reply": "", "verdict": "", "reason": "", "skipped": skip})
    else:
        if not reply_file:
            raise Problem("Give the reply as a file (--reply-file), or say why the message was not sent (--skip).")
        path = Path(reply_file).expanduser()
        try:
            if path.stat().st_size > MAX_REPLY_FILE:
                raise Problem(f"The reply file is larger than {MAX_REPLY_FILE // 1000} KB. Save only the assistant's reply.")
            reply = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            raise Problem(f"The reply file {path} could not be read.") from None
        if not reply:
            raise Problem("The reply file is empty. If the assistant said nothing, use --skip with the reason.")
        row.update({"reply": reply[:target.MAX_REPLY], "verdict": verdict, "reason": reason, "skipped": ""})
    _save(folder, data)
    left = len(_left(data))
    return f"Recorded {item_id}. {left} left." if left else f"Recorded {item_id}. That was the last one. Now run:  attack-test finish --run {folder}"


def finish(folder: Path, refusals: list[str], never_say: list[str]) -> dict:
    """Judge what was brought back. The packs are read again from where they were, so the word lists are the tool's
    own and not whatever run.json might have been made to say."""
    data = load(folder)
    joined = packs.join(data["pack_args"])
    note = ONE_CONVERSATION if data.get("one_conversation") else ""
    return run.judge_sheet(data, joined, data["target"], refusals, never_say, note=note)
