"""Attack packs: reading them, checking them, and joining several into one list.

A pack is a JSON file:

  name        what the pack is called
  about       a sentence or two for whoever opens the file
  reviewed    the date (2026-11-18) the pack was last checked against newly reported attacks. A report warns when
              that was more than six months before the run
  everywhere  word lists (regular expressions) checked against the reply to EVERY attack in the run
  attacks     messages meant to talk the assistant out of its job. Each has
                id          short, lower case, unique across every pack in a run
                category    which family of trick it belongs to
                text        the message
                before      earlier messages from the same person, for tricks that build up (optional)
                fail_if     words that would show the assistant did what was asked (optional)
                gives_way   one plain sentence on what giving way would look like (optional; shown in the report and
                            given to the model judge when there is one)
                owasp       which OWASP risk it tries, as one of the keys in owasp.py (optional)
                source      where the technique was reported, and when (optional; shown in the report)
  ordinary    messages an honest person might send that look a little like an attack. Each has id, text and
              optionally before. They must get a normal answer: the run counts any that are refused.

Every pattern is matched without regard to case, and "." matches a line break. A pack is read like code: a pattern
written to be slow on purpose could stall a run, so read a pack someone else wrote before using it.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from . import Problem, owasp

PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")   # an id, and the short name of a pack kept in packs/
MAX_FILE = 2_000_000
MAX_TEXT = 6000
MAX_PATTERN = 400
MAX_PATTERNS = 30
MAX_BEFORE = 10
MAX_ITEMS = 2000
FLAGS = re.I | re.S


def _text(value, what: str, limit: int, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Problem(f"{what} must be text of 1 to {limit} characters.")
    return value


def patterns(value, what: str) -> list[str]:
    """A list of regular expressions, each short enough to read and able to be compiled."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_PATTERNS:
        raise Problem(f"{what} must be a list of at most {MAX_PATTERNS} patterns.")
    for p in value:
        if not isinstance(p, str) or not p or len(p) > MAX_PATTERN:
            raise Problem(f"{what}: each pattern must be text of 1 to {MAX_PATTERN} characters.")
        try:
            re.compile(p, FLAGS)
        except re.error as e:
            raise Problem(f"{what}: the pattern {p!r} is not a valid regular expression ({e.msg}).") from None
    return list(value)


def read_json(path: Path, what: str):
    """A JSON file of a sensible size. Used for packs, target files and reply sheets."""
    try:
        if path.stat().st_size > MAX_FILE:
            raise Problem(f"{what} {path} is larger than {MAX_FILE // 1_000_000} MB.")
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Problem(f"There is no {what} at {path}.") from None
    except (OSError, UnicodeDecodeError):
        raise Problem(f"The {what} at {path} could not be read.") from None
    except json.JSONDecodeError as e:
        raise Problem(f"The {what} at {path} is not valid JSON (line {e.lineno}: {e.msg}).") from None


def _where(name: str) -> Path:
    """`core` means packs/core.json in this tool's folder. Anything else is a path the person typed."""
    if NAME.match(name):
        kept = PACKS_DIR / f"{name}.json"
        if kept.is_file():
            return kept
    return Path(name).expanduser()


def _item(raw, where: str, ordinary: bool, pack: str) -> dict:
    if not isinstance(raw, dict):
        raise Problem(f"{where}: each entry must be an object.")
    allowed = {"id", "text", "before"} if ordinary else {"id", "category", "text", "before", "fail_if", "gives_way", "owasp", "source"}
    extra = sorted(set(raw) - allowed)
    if extra:
        raise Problem(f"{where}: the entry {raw.get('id', '?')!r} has a field this tool does not know: {extra[0]!r}.")
    item_id = raw.get("id")
    if not isinstance(item_id, str) or not NAME.match(item_id):
        raise Problem(f"{where}: the id {item_id!r} must be lower-case letters, digits and hyphens, at most 41 long.")
    at = f"{where}, {item_id}"
    risk = raw.get("owasp", "")
    if risk and risk not in owasp.KEYS:
        raise Problem(f"{at}: 'owasp' must be one of: {', '.join(owasp.KEYS)}.")
    before = raw.get("before", [])
    if not isinstance(before, list) or len(before) > MAX_BEFORE:
        raise Problem(f"{at}: 'before' must be a list of at most {MAX_BEFORE} earlier messages.")
    return {
        "id": item_id,
        "category": "ordinary messages that must get a normal answer" if ordinary else _text(raw.get("category"), f"{at}: 'category'", 80),
        "text": _text(raw.get("text"), f"{at}: 'text'", MAX_TEXT),
        "before": [_text(b, f"{at}: each earlier message", MAX_TEXT) for b in before],
        "fail_if": [] if ordinary else patterns(raw.get("fail_if"), f"{at}: 'fail_if'"),
        "gives_way": "" if ordinary else _text(raw.get("gives_way"), f"{at}: 'gives_way'", 400, optional=True),
        "owasp": "" if ordinary else risk,
        "source": "" if ordinary else _text(raw.get("source"), f"{at}: 'source'", 300, optional=True),
        "ordinary": ordinary,
        "pack": pack,
    }


def load(name: str) -> dict:
    """One pack, checked. Raises Problem with a plain sentence if anything in it is not as it should be."""
    path = _where(name)
    raw = read_json(path, "attack pack")
    where = f"Pack {path.name}"
    if not isinstance(raw, dict):
        raise Problem(f"{where}: the file must hold one object.")
    pack = _text(raw.get("name"), f"{where}: 'name'", 80)
    attacks, ordinary = raw.get("attacks", []), raw.get("ordinary", [])
    if not isinstance(attacks, list) or not isinstance(ordinary, list) or len(attacks) + len(ordinary) > MAX_ITEMS:
        raise Problem(f"{where}: 'attacks' and 'ordinary' must be lists, of at most {MAX_ITEMS} entries together.")
    if not attacks and not ordinary:
        raise Problem(f"{where}: there is nothing in it to send.")
    reviewed = raw.get("reviewed", "")
    if reviewed:
        try:
            if not isinstance(reviewed, str) or date.fromisoformat(reviewed).isoformat() != reviewed:
                raise ValueError
        except ValueError:
            raise Problem(f"{where}: 'reviewed' must be a date written like 2026-11-18.") from None
    return {
        "name": pack,
        "reviewed": reviewed,
        "about": _text(raw.get("about"), f"{where}: 'about'", 2000, optional=True),
        "everywhere": patterns(raw.get("everywhere"), f"{where}: 'everywhere'"),
        "items": [_item(a, where, False, pack) for a in attacks] + [_item(o, where, True, pack) for o in ordinary],
    }


def join(names: list[str], only: list[str] | None = None, skip: list[str] | None = None, per_kind: int | None = None) -> dict:
    """Several packs as one run: the attacks first, then the ordinary messages. `only` and `skip` take categories or
    ids. `per_kind` keeps the first few of each kind, for a quick pass: a pack lists its plainest tricks first. An id
    used twice is refused, since the report would not say which was meant."""
    if not names:
        raise Problem("Name at least one pack, for example: --pack core")
    packs = [load(n) for n in names]
    seen: dict[str, str] = {}
    for p in packs:
        for item in p["items"]:
            if item["id"] in seen:
                raise Problem(f"The id {item['id']!r} is in both {seen[item['id']]!r} and {p['name']!r}. Rename one.")
            seen[item["id"]] = p["name"]
    items = [i for p in packs for i in p["items"]]
    known = {i["id"] for i in items} | {i["category"] for i in items}
    for word in (only or []) + (skip or []):
        if word not in known:
            raise Problem(f"{word!r} is not a category or an id in these packs. Categories: {', '.join(categories(items))}.")
    if only:
        items = [i for i in items if i["id"] in only or i["category"] in only]
    if skip:
        items = [i for i in items if i["id"] not in skip and i["category"] not in skip]
    if per_kind is not None:
        if not 1 <= per_kind <= 50:
            raise Problem("--per-kind must be from 1 to 50.")
        seen_of: dict[str, int] = {}
        few = []
        for i in items:
            seen_of[i["category"]] = seen_of.get(i["category"], 0) + 1
            if seen_of[i["category"]] <= per_kind:
                few.append(i)
        items = few
    if not items:
        raise Problem("Nothing is left to send after --only and --skip.")
    everywhere = list(dict.fromkeys(x for p in packs for x in p["everywhere"]))
    return {"packs": [p["name"] for p in packs], "reviews": [{"pack": p["name"], "reviewed": p["reviewed"]} for p in packs], "everywhere": everywhere,
            "items": [i for i in items if not i["ordinary"]] + [i for i in items if i["ordinary"]]}


def categories(items: list[dict]) -> list[str]:
    return list(dict.fromkeys(i["category"] for i in items))
