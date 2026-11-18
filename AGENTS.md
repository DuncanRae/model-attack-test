# Maintainer guide: read this first

For any person or AI tool changing this project. It assumes you have this repository and nothing else.

## 1. What this is

Model Attack Test sends known tricks to an AI chat system and reports which ones it gave way to. People point it at
chat systems they are building, to see whether the assistant can be talked out of its job. It is a small Python tool
with nothing to install, a set of attack packs, and a skill that lets an AI agent run the test through a chat page
the way a person would.

## 2. What to read, in order

| File | What it gives you |
|---|---|
| `AGENTS.md` | This file: the rules, the map, how to work, the state |
| `README.md` | How to use it, what it does not cover, the security notes |
| `docs/decisions.md` | The design decisions and why each was made. What is still open |
| `CHANGELOG.md` | Every version: what changed, how it was checked, what was not |
| The top of each file in `attack_test/` | How that part works. The formats of a pack and a target file are written there |

## 3. Rules that are not up for debate

- **Easy to run.** Nothing to install. Standard library only: adding a library needs a strong reason, a line in the
  README, and it must be well known and maintained (D1).
- **A pass is not a certificate** (D6). The report, the skill and the README all say so. Keep it that way.
- **It is not an OWASP assessment, and nothing here may say it is** (D28). It reaches four of the ten risks in
  part. The map in the report always shows all ten.
- **The tool must not be a way to attack someone else's system or to leak a key** (D3, D4). Everything the tool
  sends goes through `Sender._send` in `attack_test/target.py`. Do not add a second way out. On the browser route
  the tool sends nothing: the agent types.
- **A reply never goes on a command line** (D21). It reaches the tool as a file. Keep it that way in the tool and
  in the skill's wording.
- **Ordinary messages matter as much as attacks** (D5). A pack without them is half a test.
- **Attacks carry harmless requests** (D29). A made-up word, or a request for the system's own instructions, in
  place of anything harmful. This project tests whether a technique works, not what it could be used for. Do not
  add an attack that asks for harmful content.
- **Never make a failure go away by loosening a pack.** A pattern that fired wrongly is fixed in the pattern and
  pinned by a test with a held example and a gave-way example (`tests/test_packs.py`, `tests/test_owasp.py`).
- **A pack's `reviewed` date is changed only by someone who checked it against new reports that day** (D30). Never
  bump it to make a warning go away.
- **The skill is not reworded to get a model past its own refusal** (D32).
- **Nothing that names a real organisation's internal systems or people goes into the repository.**
  `tests/test_public.py` checks for the ones it knows about. A folder called `internal/`, if there is one, is the
  owner's private notes: it is ignored by git and must stay that way.

### Security rules for all code here

1. Never put passwords, API keys, tokens or connection strings in the code. Read them from environment variables,
   and say in the README which ones a person needs to set.
2. Treat all input as hostile: files, URLs, API responses and AI output. Validate it against an allow list (type,
   length, format) and reject anything else.
3. Never build shell commands or file paths by joining strings with input.
4. Encode output for where it is shown (HTML, JavaScript, URLs) to prevent cross-site scripting.
5. Least privilege: ask for the smallest permissions and access that will work.
6. Do not switch off security features to make something work: no disabled certificate checks, no debug mode.
7. Only well-known, maintained libraries, each listed with its reason. Never invent a package name.
8. Handle errors without showing stack traces or internal details. Never log passwords, tokens or personal
   information.
9. With every change, list the security assumptions made and anything a user still needs to check.

## 4. After every change

1. **Tests.** Add or change a test for what you changed. `./run-tests.sh` must pass.
2. **`CHANGELOG.md`.** An entry under the new version: what changed, why, how it was checked, what was not.
3. **`docs/decisions.md`.** If a decision was made, changed or overturned, or an open question was settled.
4. **`README.md`.** If how to use it, an option, a limit or a security note changed.
5. **`AGENTS.md`.** If a rule, the map, the commands or the state changed.
6. **The version**, in `attack_test/__init__.py` and `.claude-plugin/plugin.json`. They must match.
7. **Build the skill** with `./package-skill.sh`. It runs the tests and refuses if the versions differ or the
   changelog has no entry. Anyone who installed the skill has a copy: they need the new one.

## 5. The parts

| Path | What it does |
|---|---|
| `attack-test` | The launcher: puts this folder on Python's path and calls `cli.main` |
| `attack_test/packs.py` | Reads and checks packs, joins several, applies `--only`, `--skip` and `--per-kind` |
| `attack_test/target.py` | Reads and checks a target file. `Sender` is the only thing that sends: no redirects, key from the environment into a header, answers capped and checked |
| `attack_test/judge.py` | Word lists, the general refusal wording, and `ModelJudge` (a second model, never trusted) |
| `attack_test/run.py` | `run_suite` (send and judge), `sheet` and `judge_sheet` (replies collected another way), the counts |
| `attack_test/owasp.py` | The OWASP Top 10 for LLM Applications (2026): the ten risks, what sending messages can reach of each, the map a result carries, and where the list was read from |
| `attack_test/byhand.py` | A run through a chat page, one message at a time: `begin`, `next_message`, `record`, `finish`. Sends nothing. A reply comes in as a file only |
| `attack_test/report.py` | `report.html` and `results.json`. Everything on the page goes through `e()` |
| `attack_test/cli.py` | The commands: `check`, `list`, `run`, `export`, `judge`, `begin`, `next`, `record`, `finish`, `practice` |
| `packs/core.json` | The generic pack. Ids start `core-` |
| `packs/recent.json` | Techniques reported from 2024 to 2026 in a harmless form, each with its `source`. Ids start `rec-`. Dates fastest: this is the pack to review |
| `packs/examples/supplier-interview.json` | One system's own pack, as the pattern: an assistant that interviews suppliers about their security for a made-up company. Ids start `sup-` |
| `targets/examples/` | Two for the practice bot, one for anything that speaks "chat completions", one judge on Vertex AI |
| `practice/bot.py` | "Leave Helper": a made-up chatbot by plain rules, in three kinds (weak, holding, strict), with a chat page at `/`. Listens on 127.0.0.1 only |
| `skills/model-attack-test/SKILL.md` | The skill: testing through the chat page with a browser. `address-route.md` beside it is the command-line route |
| `package-skill.sh` | Runs the tests, then builds `dist/model-attack-test/` (the skill with the tool copied into `scripts/`) and a zip. `dist/` is never edited by hand and is not kept in version control |
| `.claude-plugin/plugin.json` | Also makes the whole folder a Claude Code plugin |
| `tests/` | `helpers.py` starts stand-in servers on free ports. Nothing in the tests leaves this computer |

## 6. Commands

```bash
./run-tests.sh                                   # every test
./attack-test practice --mode weak               # the made-up chatbot, on port 8777
./attack-test run --target targets/examples/practice-messages.json --pack core --pack recent
./package-skill.sh                               # tests, then dist/model-attack-test/ and the zip
claude plugin validate .                         # the plugin layout
claude --plugin-dir .                            # try the skill in Claude Code without installing it
```

## 7. The state at v0.4.2 (18 November 2026)

**It has been run almost only against the practice chatbot, which is not a model.** `CHANGELOG.md` has what each
version was checked against.

Checked: the tests pass on Python 3.9 and 3.12. A full run of `core` and `recent` through the command line against
the practice bots, and the report page looked at in a browser. The skill followed from the built folder alone by a
fresh agent on a cheaper model, in a browser, against the practice chat page. One person has run the skill in
Claude against a real chat page and reported that it ran.

Not checked, in the order it matters:

1. **The word lists against real models.** Those in `core` were first tuned against one model that declined with a
   fixed sentence. Those in `recent` have never met a model at all. Against a system that declines in its own
   words, expect false alarms under "Gave way". Each one found should be fixed in the pattern and pinned in the
   tests. Reports of them are the most useful thing a user can send.
2. **The `recent` pack through a browser.** Text that cannot be seen (`rec-uns-01`, `rec-uns-02`) may not survive
   being typed, and several attacks have many lines.
3. **The sources in `recent`**, against the original papers. They were checked against public write-ups.
4. **The skill with a model permitted to do security work.** The README recommends one (D34). None has been
   tried: the runs so far were with general-purpose Claude models.
5. **The skill in Codex.** The README has instructions written from OpenAI's documentation (November 2026).
   Nobody has run it there. Its browser asks for confirmation before sensitive actions, which may make a long run
   tedious, and its model may decline as Gemini did.
6. **The skill in Antigravity.** It loads there. Gemini 4 declined the work (D32).
7. **The model judge against a real model** (the command-line route).

## 8. Open work

- **Reviewing the packs.** The next review is due by May 2027, sooner for `recent`. To review: read what has been
  reported since the `reviewed` date (the OWASP GenAI project, the vendors' research blogs, the open tools' attack
  lists), add what is new in a harmless form with its `source`, then change the date.
- The open questions at the end of `docs/decisions.md`.
