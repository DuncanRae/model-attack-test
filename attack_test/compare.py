"""Comparing two runs: what a change to the system fixed, what it broke, and what is still wrong.

    attack-test compare OLDER NEWER

Each is a run's folder or its results.json. Messages are matched by id, so both runs should use the same packs.
A results file is read as input like any other: only the few fields needed are taken, and only known words.
"""
from __future__ import annotations

from pathlib import Path

from . import Problem
from .packs import ITEM, read_json

BAD, GOOD = ("failed", "blocked", "leaked"), ("held", "answered")
ORDER = {"high": 0, "medium": 1, "low": 2, "": 3}


def load(where: str) -> dict:
    path = Path(where).expanduser()
    path = path / "results.json" if path.is_dir() else path
    data = read_json(path, "run")
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or data.get("tool") != "model-attack-test":
        raise Problem(f"{path} is not a results.json written by this tool.")
    kept = {}
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("id"), str) and ITEM.match(r["id"]) and r.get("verdict") in BAD + GOOD + ("error", "not run", "not reached"):
            kept[r["id"]] = {"id": r["id"], "verdict": r["verdict"], "severity": r.get("severity") if r.get("severity") in ORDER else "",
                             "category": str(r.get("category", ""))[:80], "text": " ".join(str(r.get("text", "")).split())[:160]}
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    return {"name": str(target.get("name", "?"))[:80], "started": str(data.get("started", "?"))[:40], "version": str(data.get("version", "?"))[:20],
            "packs": [str(p)[:80] for p in data.get("packs", []) if isinstance(p, str)][:20], "rows": kept}


def compare(older: dict, newer: dict) -> dict:
    """Every message in both runs, sorted into what changed. A message one run could not judge is set aside."""
    both = [i for i in newer["rows"] if i in older["rows"]]
    pick = lambda was, now: sorted((dict(newer["rows"][i], was=older["rows"][i]["verdict"]) for i in both
                                    if older["rows"][i]["verdict"] in was and newer["rows"][i]["verdict"] in now),
                                   key=lambda r: (ORDER[r["severity"]], r["id"]))
    judged = BAD + GOOD
    return {"older": {k: older[k] for k in ("name", "started", "version", "packs")}, "newer": {k: newer[k] for k in ("name", "started", "version", "packs")},
            "worse": pick(GOOD, BAD), "fixed": pick(BAD, GOOD), "still_wrong": pick(BAD, BAD), "still_fine": len(pick(GOOD, GOOD)),
            "not_comparable": sum(1 for i in both if older["rows"][i]["verdict"] not in judged or newer["rows"][i]["verdict"] not in judged),
            "only_in_newer": sorted(i for i in newer["rows"] if i not in older["rows"]),
            "only_in_older": sorted(i for i in older["rows"] if i not in newer["rows"])}


def text(c: dict) -> str:
    def block(title: str, rows: list[dict]) -> list[str]:
        return [f"{title}: {len(rows)}"] + [f"  {r['id']}  [{r['severity'] or 'ordinary'}]  {r['was']} -> {r['verdict']}  {r['text']}" for r in rows]
    out = [f"Older: {c['older']['name']}, {c['older']['started']}, packs {', '.join(c['older']['packs'])}",
           f"Newer: {c['newer']['name']}, {c['newer']['started']}, packs {', '.join(c['newer']['packs'])}", ""]
    out += block("Got worse (held or answered before, not now)", c["worse"]) + [""]
    out += block("Fixed (wrong before, right now)", c["fixed"]) + [""]
    out += block("Still wrong", c["still_wrong"]) + [""]
    out.append(f"Still right: {c['still_fine']}. Could not be compared (no reply or not reached in one of the runs): {c['not_comparable']}.")
    if c["only_in_newer"] or c["only_in_older"]:
        out.append(f"Only in the newer run: {len(c['only_in_newer'])}. Only in the older run: {len(c['only_in_older'])}. The runs did not use the same messages.")
    if c["older"]["name"] != c["newer"]["name"]:
        out.append("The two runs name different systems. Check they are the same one.")
    out.append("A model's answers vary from run to run, so one message changing sides is a pointer, not proof. Run each side with --repeat to be sure.")
    return "\n".join(out)
