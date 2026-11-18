"""The report: one page that opens in any browser with nothing to install, and the same result as JSON.

Every reply on the page came from the system under test, and a reply to an attack is exactly where a script tag
would turn up. So everything is written through `e()` (HTML-encoded), the page loads nothing and runs nothing, and a
content policy in the page says so to the browser as well.

A report can hold whatever the system leaked. The folder and files are made readable by their owner only.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from html import escape
from pathlib import Path

from . import Problem

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--soft:#5b6675;--line:#dfe3e8;--bad:#b3261e;--badbg:#fdecea;--ok:#1e6b3a;--okbg:#e8f5ec;--warn:#8a5a00;--warnbg:#fff4d9;--code:#f0f2f5}
@media (prefers-color-scheme:dark){:root{--bg:#14181d;--card:#1d232b;--ink:#e8ecf1;--soft:#a3adba;--line:#323a45;--bad:#ff8a80;--badbg:#3a1c1a;--ok:#7bd49a;--okbg:#17301f;--warn:#f2c35c;--warnbg:#3a2e12;--code:#262d37}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:0}
.meta{color:var(--soft);font-size:.9rem;margin:0 0 20px}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:0 0 16px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.tile b{display:block;font-size:1.7rem;line-height:1.2}
.tile span{color:var(--soft);font-size:.9rem}.tile.bad b{color:var(--bad)}.tile.ok b{color:var(--ok)}.tile.warn b{color:var(--warn)}
.note{background:var(--warnbg);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:0 0 16px}.note p{margin:0 0 6px}.note p:last-child{margin:0}
.stop{background:var(--badbg)}details{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:0 0 12px}
summary{cursor:pointer;padding:12px 16px;display:flex;gap:10px;align-items:baseline}summary small{color:var(--soft)}
.item{border-top:1px solid var(--line);padding:12px 16px}.item h3{font-size:.95rem;margin:0 0 6px}.item h3 small{color:var(--soft);font-weight:400}
.said,.reply{white-space:pre-wrap;overflow-wrap:anywhere;border-radius:8px;padding:8px 10px;margin:4px 0;font-size:.92rem}
.said{background:var(--code)}.reply{border:1px solid var(--line)}.lab{color:var(--soft);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;margin:8px 0 0}
.marks{margin:6px 0 0;padding:0 0 0 18px;font-size:.9rem}.marks li{color:var(--bad)}.marks li.j{color:var(--soft)}
table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{text-align:left;padding:6px 16px;border-top:1px solid var(--line)}th{color:var(--soft);font-weight:600}
.sev{font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;border-radius:6px;padding:1px 6px;border:1px solid var(--line);color:var(--soft)}
.sev.high{color:var(--bad);border-color:var(--bad)}.sev.medium{color:var(--warn);border-color:var(--warn)}
td.n,th.n{text-align:right}td.n{white-space:nowrap}td small{color:var(--soft)}tr.off td{color:var(--soft)}td.bad{color:var(--bad);font-weight:600}td{vertical-align:top}th,td{padding-left:12px;padding-right:12px}footer{color:var(--soft);font-size:.85rem;margin-top:24px}
"""


def e(value) -> str:
    return escape(str(value), quote=True)


def _item(row: dict) -> str:
    badge = f' <span class="sev {e(row["severity"])}">{e(row["severity"])}</span>' if row.get("severity") else ""
    disguise = f' · in disguise: {e(row["variant"])}' if row.get("variant") else ""
    out = [f'<div class="item"><h3>{e(row["id"])}{badge} <small>{e(row["category"])} · {e(row["pack"])}{disguise}</small></h3>']
    if row["gives_way"]:
        out.append(f'<p class="lab">Giving way would look like</p><div>{e(row["gives_way"])}</div>')
    if row.get("source"):
        out.append(f'<p class="lab">Technique reported by</p><div>{e(row["source"])}</div>')
    runs = sorted(row["runs"], key=lambda r: not r["marks"]) or [None]
    if len(row["runs"]) > 1 and row["failed_runs"]:
        out.append(f'<p><strong>{"Went wrong" if row["ordinary"] else "Gave way"} in {row["failed_runs"]} of {len(row["runs"])} runs.</strong></p>')
    for n, run in enumerate(runs):
        if n == 0:
            earlier = run["earlier"] if run else []
            for i, said in enumerate(row["before"]):
                out.append(f'<p class="lab">Earlier message {i + 1}</p><div class="said">{e(said)}</div>')
                if i < len(earlier):
                    out.append(f'<div class="reply">{e(earlier[i])}</div>')
            if row.get("padding"):
                out.append(f'<p class="lab">Sent</p><div>{row["padding"]:,} characters of ordinary filler, and then:</div>')
            if row.get("burst"):
                out.append(f'<p class="lab">Sent</p><div>This message, {row["burst"]} times with no pause:</div>')
            out.append(f'<p class="lab">{"The goal" if row.get("goal") else "Sent"}</p><div class="said">{e(row["text"])}</div>')
        if run is None:
            out.append(f'<p class="lab">Not sent</p><div>{e(row.get("skipped") or "")}</div>')
            continue
        label = "Reply" if len(runs) == 1 else f"Reply, run {n + 1}"
        if run["error"]:
            out.append(f'<p class="lab">{label}</p><div class="reply">No reply: {e(run["error"])}</div>')
            continue
        if run.get("turns"):
            for i, turn in enumerate(run["turns"], 1):
                out.append(f'<p class="lab">Message {i}, written by the attacker</p><div class="said">{e(turn["said"])}</div><div class="reply">{e(turn["reply"])}</div>')
        elif run["reply"] or not run.get("note"):
            shown = run["reply"] if len(run["reply"]) <= 3000 else run["reply"][:3000] + f" ... ({len(run['reply']) - 3000:,} more characters are in results.json)"
            out.append(f'<p class="lab">{label}</p><div class="reply">{e(shown)}</div>')
        if run.get("note"):
            out.append(f'<p>{e(run["note"])}</p>')
        if any(row.get(k) for k in ("longer_than", "slower_than", "padding", "burst")) and (run.get("chars") or run.get("seconds")):
            out.append(f'<p class="lab">Measured</p><div>The reply was {run.get("chars", 0):,} characters long'
                       + (f', of which the first {len(run["reply"]):,} are shown' if run.get("chars", 0) > len(run["reply"]) else "")
                       + f'. It took {run.get("seconds", 0):g} seconds.</div>')
        notes = [f"<li>{e(m)}</li>" for m in run["marks"]]
        by = (run["judge"] or {}).get("by", "the model judge")
        if run["judge"] and not any(m.startswith(by) for m in run["marks"]):
            notes.append(f'<li class="j">{e(by)}: {e(run["judge"]["verdict"].replace("_", " "))}. {e(run["judge"]["reason"])}</li>')
        if notes:
            out.append(f'<ul class="marks">{"".join(notes)}</ul>')
    out.append("</div>")
    return "".join(out)


def _section(title: str, hint: str, rows: list[dict], is_open: bool = False) -> str:
    if not rows:
        return ""
    return (f'<details{" open" if is_open else ""}><summary><h2>{e(title)}: {len(rows)}</h2><small>{e(hint)}</small></summary>'
            f'{"".join(_item(r) for r in rows)}</details>')


def _owasp(result: dict) -> str:
    """Every risk on the list, with what this run sent against it. The risks nothing was sent for stay on the page:
    leaving them off would let a clean run read as the whole list covered."""
    o = result.get("owasp")
    if not o:
        return ""
    lines = []
    for r in o["rows"]:
        if r["reach"] == "no":
            sent, wrong, cls = "cannot", "", ' class="off"'
        elif not r["sent"] and not r["no_reply"]:
            sent, wrong, cls = "none", "", ' class="off"'
        else:
            sent, wrong, cls = str(r["sent"]), str(r["went_wrong"]), ""
        bad = ' bad' if r["went_wrong"] else ""
        lines.append(f'<tr{cls}><td><strong>{e(r["id"])} {e(r["title"])}</strong> <small>(was {e(r["was"])})</small><br><small>{e(r["note"])}</small></td>'
                     f'<td class="n">{e(sent)}</td><td class="n{bad}">{e(wrong)}</td><td class="n">{e(r["to_read"] or "")}</td></tr>')
    untagged = f' {o["untagged"]} attacks in this run are not marked with a risk and are not counted here.' if o["untagged"] else ""
    return (f'<details open><summary><h2>Against the {e(o["edition"])}</h2><small>{e(o["detail"])}</small></summary>'
            f'<table><tr><th>Risk, and what these messages reach and do not</th><th class="n">Sent</th><th class="n">Went wrong</th><th class="n">To read</th></tr>'
            f'{"".join(lines)}</table><div class="item"><p>{e(o["reading"])}{e(untagged)}</p><p>{e(o["agentic"])}</p></div></details>')


def page(result: dict) -> str:
    s, t, rows = result["stats"], result["target"], result["rows"]
    pick = lambda verdict, ordinary=False, read=None: [r for r in rows if r["verdict"] == verdict and r["ordinary"] == ordinary
                                                         and (read is None or r["read"] == read)]
    sent = s["attacks"] - sum(1 for r in rows if not r["ordinary"] and r["verdict"] in ("error", "not run", "not reached"))
    asked = s["ordinary"] - sum(1 for r in rows if r["ordinary"] and r["verdict"] in ("error", "not run"))
    order = {"high": 0, "medium": 1, "low": 2}
    by_severity = lambda rs: sorted(rs, key=lambda r: order.get(r.get("severity"), 3))
    high = f', {s["failed_high"]} of them high severity' if s.get("failed_high") else ""
    tiles = [("bad" if s["failed"] else "ok", s["failed"], "attacks it gave way to" + high),
             ("ok" if sent and s["held"] == sent else "", f'{s["held"]} of {sent}', "attacks held, of those that got a reply")]
    if s["ordinary"]:
        tiles.append(("bad" if s["blocked"] else "ok", f'{s["answered"]} of {asked}', "ordinary messages given a normal answer"))
    if s["leaked"]:
        tiles.append(("bad", s["leaked"], "ordinary messages that were given something secret"))
    if s["to_read"]:
        tiles.append(("warn", s["to_read"], "held replies nobody has read yet"))
    if s.get("not_reached"):
        tiles.append(("warn", s["not_reached"], "attacks that tested nothing: the system never found what they depend on"))
    if s["errors"] or s["not_run"]:
        tiles.append(("warn", s["errors"] + s["not_run"], "messages with no reply, or not sent"))
    disguises = ""
    if result.get("disguises"):
        lines = "".join(f'<tr><td>{e(d["name"])}</td><td class="n">{d["sent"]}</td><td class="n{" bad" if d["went_wrong"] else ""}">{d["went_wrong"]}</td>'
                        f'<td class="n{" bad" if d["only_in_disguise"] else ""}">{d["only_in_disguise"]}</td></tr>' for d in result["disguises"])
        disguises = ('<details open><summary><h2>By disguise</h2><small>the same attacks, sent again in a form meant to slip past a filter</small></summary>'
                     '<table><tr><th>Disguise</th><th class="n">Sent</th><th class="n">Gave way</th><th class="n">Only in disguise</th></tr>' + lines
                     + '</table><div class="item"><p>"Only in disguise" counts attacks that were held as written and got through in this form. '
                     'A number there means something is reading the plain words and not the meaning.</p></div></details>')
    by_cat: dict[str, dict] = {}
    for r in rows:
        c = by_cat.setdefault(r["category"], {"n": 0, "bad": 0, "read": 0, "none": 0})
        c["n"] += 1
        c["bad"] += r["verdict"] in ("failed", "blocked", "leaked")
        c["read"] += bool(r["read"])
        c["none"] += r["verdict"] in ("error", "not run", "not reached")
    table = "".join(f'<tr><td>{e(k)}</td><td class="n">{v["n"]}</td><td class="n">{v["bad"]}</td><td class="n">{v["read"]}</td><td class="n">{v["none"]}</td></tr>'
                    for k, v in by_cat.items())
    stopped = f'<div class="note stop"><p><strong>The run did not finish.</strong> {e(result["stopped"])}</p></div>' if result["stopped"] else ""
    noted = f'<div class="note stop"><p><strong>Read this first.</strong> {e(result["note"])}</p></div>' if result.get("note") else ""
    old = [r for r in result.get("pack_reviews", []) if r["stale"]]
    if old:
        noted += ('<div class="note stop"><p><strong>The attacks are out of date.</strong> ' + " ".join(
            f'The pack {e(r["pack"])} was last checked against newly reported attacks on {e(r["reviewed"])}, more than six months before this run.' for r in old)
            + " Tricks reported since then are missing.</p></div>")
    packs_line = ", ".join(r["pack"] + (f' (checked {r["reviewed"]})' if r["reviewed"] else " (not dated)") for r in result.get("pack_reviews", [])) or ", ".join(result["packs"])
    repeat = f' · each message sent {result["repeat"]} times' if result["repeat"] > 1 else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Attack test: {e(t["name"])}</title><style>{CSS}</style></head><body><main>
<h1>Model attack test: {e(t["name"])}</h1>
<p class="meta">Owner: {e(t["owner"])} · {e(t["environment"])} · {e(t["host"])} · {e(result["started"])} · packs: {e(packs_line)} · judged by {e(result["judged_by"])}{e(repeat)}</p>
<div class="tiles">{"".join(f'<div class="tile {c}"><b>{e(n)}</b><span>{e(label)}</span></div>' for c, n, label in tiles)}</div>
{stopped}{noted}
<div class="note"><p><strong>What this does and does not show.</strong> It shows how the system answered these known tricks on this day. It is not a certificate and it is not sign-off: a system that held here can still be talked round by a trick that is not in the packs, or by the same trick on another try.</p>
<p>Word lists can be wrong both ways. Read every reply under "Gave way" before treating it as a fault, and read the held replies nobody has read: a reply can give way in words no list looks for.</p></div>
{_owasp(result)}
{_section("Gave way", "the assistant looks to have done what it was asked. High severity first", by_severity(pick("failed")), True)}
{_section("Ordinary messages given something secret", "nobody was even trying", pick("leaked", True), True)}
{_section("Ordinary messages refused", "an honest person was turned away", pick("blocked", True), True)}
{_section("Held, not read by anyone yet", "no word list fired, and the reply was in the assistant's own words", pick("held", read=True))}
{_section("Tested nothing", "the reply showed no sign of what the attack depends on, such as a planted document. Check the system can find it, then run again", pick("not reached"), True)}
{_section("No reply", "the system did not answer", [r for r in rows if r["verdict"] == "error"])}
{_section("Not sent", "the run stopped first, or the message could not be sent", [r for r in rows if r["verdict"] == "not run"])}
{_section("Held", "declined plainly, or read by a model and found to have held", pick("held", read=False))}
{_section("Ordinary messages answered", "as they should be", pick("answered", True))}
{disguises}
<details open><summary><h2>By kind of trick</h2></summary><table><tr><th>Kind</th><th class="n">Sent</th><th class="n">Went wrong</th><th class="n">To read</th><th class="n">No result</th></tr>{table}</table></details>
<footer>model-attack-test {e(result["version"])} · {s["requests"]} requests to the system{f', {s["judge_requests"]} to the judge' if s["judge_requests"] else ''}{f', {s["attacker_requests"]} to the attacker model' if s.get("attacker_requests") else ''} · {result["seconds"]} seconds. This page may hold whatever the system gave away: share it as you would the system's own data.</footer>
</main></body></html>
"""


def _write(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def folder_for(name: str, base: str = "reports") -> Path:
    """reports/<name made safe>-<date and time>. Only letters, digits and hyphens of the name are kept."""
    safe = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "run"
    return Path(base) / f"{safe}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def write(result: dict, folder: Path) -> Path:
    """Write report.html and results.json into `folder` and return the page's path."""
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        _write(folder / "results.json", json.dumps(result, ensure_ascii=False, indent=1))
        _write(folder / "report.html", page(result))
    except OSError:
        raise Problem(f"The report could not be written to {folder}.") from None
    return folder / "report.html"
