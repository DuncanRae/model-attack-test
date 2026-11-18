# Changelog

Every version: what changed, how it was checked, and what was not.

## v0.4.2 (18 November 2026)

**What changed**

- **A "Which model" section in the README.** A model permitted to do security work is the better choice where one
  is available. Of the general-purpose models in November 2026: the Claude 5.5 models and Claude Fable 5.2 seem to
  work, Gemini 4 declined, and OpenAI's models have not been tested (D34).

**How it was checked**

- The Claude and Gemini lines are what one person saw when running the skill. Nothing new was run for this version.

**What was not checked**

- Any model permitted to do security work. Any OpenAI model.

## v0.4.1 (18 November 2026)

**What changed**

- **Instructions for Codex** in the README: where the skill folder goes (`~/.agents/skills/`), that the browser
  route needs the Codex desktop app because the CLI and IDE extension have no browser, how to let its browser reach
  your system and sign in, and how to ask for the skill. A table says where each agent stands.

**How it was checked**

- Against OpenAI's documentation on 18 November 2026: the skills page for where skills are read from and how one is
  asked for, and the browser page for what the built-in browser can do and where it is available.

**What was not checked**

- **The skill has not been run in Codex.** The instructions are from documentation only. Whether its model will do
  the work, and how often its browser stops to ask for confirmation, are not known.

## v0.4.0 (18 November 2026)

The first public version.

**What changed**

- Everything that named the organisation the tool began in, its systems or its people was removed. The example pack
  (`packs/examples/supplier-interview.json`) now uses a made-up company, Acme, and a made-up competitor.
- `tests/test_public.py` fails if one of those names comes back into a file that would be published (D33).
- An MIT licence.
- The maintainer guide, design decisions and this changelog were rewritten for anyone picking the project up.

**How it was checked**

- The tests, on Python 3.9 and 3.12, including the new one.
- A search of every published file for the names that were removed, and for keys, tokens, e-mail addresses and
  paths on anyone's computer.
- The example pack still loads, and its word lists still compile, after the renaming.

**What was not checked**

- Nothing new was run against a model. The state of the word lists is as in v0.3.0.

## v0.3.0 (18 November 2026)

**What changed**

- **An OWASP coverage map in every report** (`attack_test/owasp.py`). All ten risks of the OWASP Top 10 for LLM
  Applications 2026, each with how many messages were sent against it, how many went wrong, and what sending
  messages can and cannot reach of it. Risks with nothing sent stay in the table. The same map is in `results.json`.
- **Every attack in the three packs is marked with its risk.** `core`: 49 prompt injection, 14 hidden context,
  6 output handling, 5 sensitive information. A pack's own attacks can be marked the same way (`"owasp"`).
- **A new pack, `recent`**: 20 attacks and 3 ordinary messages, for techniques reported from 2024 to 2026: Policy
  Puppetry, Sockpuppetting, the Context Compliance Attack, many-shot, Crescendo, Echo Chamber, EchoLeak, indirect
  injection in a web page, a tool result and a document, Unicode tag smuggling, Skeleton Key, Deceptive Delight and
  Bad Likert Judge. Each is in a harmless form (D29) and names its source.
- **Packs carry a review date**, and a report says so when it is more than six months old (D30).
- **The skill's quick pass** is the first two of each kind from `core` and `recent` (30 messages), and it is told
  to read out the OWASP rows that were not tried and never to say a system "passed OWASP".

**How it was checked**

- 77 tests, on Python 3.9 and 3.12. The new ones cover the list itself, that every shipped attack has a risk and
  every pack a date, the six-month warning, the map's counts in a real run, that the page keeps the untested rows,
  eight pinned pairs for the new patterns (a refusal that repeats the request, and a reply that gave way), and that
  the two practice bots that hold set off nothing in `recent`.
- A full run of `core` and `recent` through the command line against the weak practice bot: 48 of 94 gave way, and
  the map showed 61 sent for LLM01, 5 for LLM02, 21 for LLM08, 7 for LLM10 and none for the other six.
- The report page was looked at in a browser at a narrow width.
- OWASP's own page for the 2026 edition was found (v1.0, 3 August 2026). It is a download only, so the ten titles
  were taken from two write-ups that agree. OWASP's list page still showed the 2025 edition that day.

**Results from use**

- **Claude:** one person ran the skill against a real chat page and reported that it ran, after asking them to
  confirm they had authorisation.
- **Antigravity with Gemini 4:** the skill loaded and the model declined the work: "Sorry, I cannot fulfill your
  request to run active attack tests, prompt injections, or jailbreak attempts against the site, even with
  authorization or ownership." Nothing was changed in answer to it (D32).

**What was not checked**

- **The `recent` pack against any real model.** Its word lists are first drafts.
- **The `recent` pack through a browser**, where invisible text may be lost in typing.
- The technique names and dates against the original papers, and the 2026 titles against OWASP's own document.

## v0.2.0 (18 November 2026)

A skill that can be loaded into Claude or Antigravity, controls a browser, and uses an AI chat the way a person
would.

**What changed**

- **The skill is about the chat page.** The agent opens the page, the person signs in, it learns the page with one
  harmless message, then sends each message, reads the reply and brings it back. The command-line route is in
  `address-route.md` beside it.
- **Four commands for that**: `begin`, `next`, `record`, `finish` (`attack_test/byhand.py`). The tool hands out one
  message at a time and sends nothing itself. The run is a file in a folder, so it carries on after a stop.
- **A reply reaches the tool only as a file** (D21), and the agent's own reason is limited to plain characters.
- **The agent's reading of each reply is kept** and treated like the second-model judge (D22).
- **`--per-kind N`** keeps the first N of each kind, for a quick pass. **`--one-conversation`** for a system that
  gives no way to start a new one: the report says so at the top (D24).
- **`package-skill.sh`** builds `dist/model-attack-test/` (the skill with the tool inside it) and a zip (D19).
- **The practice chatbot has a chat page** at `http://127.0.0.1:8777/`.

**How it was checked**

- 65 tests. The new ones cover the whole loop from `begin` to a report, the order for one conversation, what
  `record` refuses (a reply not in a file, an unknown id or verdict, a reason with shell characters in it), a run
  file changed to bring its own word lists or message, and the practice page.
- **The skill was followed by a fresh agent on a cheaper model that was given only the built skill folder**, in a
  browser, against the weak practice chatbot's page: 9 messages, all sent, read and recorded, with a new
  conversation each time, a two-message build-up and a message with a line break. It took about two and a half
  minutes. Its replies and verdicts were checked against the run folder afterwards.
- That trial found eight places where the skill made the agent guess. All were fixed: the exit code of `finish`,
  how the count of messages was worded, writing paths out in full, saying plainly when a message is an ordinary
  one, telling the assistant's words from one's own on a page with no labels, an assistant that echoes, no
  apostrophes in a reason, and what is in `results.json`.

**What was not checked**

- The fixes to the skill's wording, by a second trial. `--one-conversation` through a browser. The zip uploaded to
  Claude on the web.

## v0.1.0 (18 November 2026)

The first version. It began as the attack suite of one in-house assistant and was made into a tool of its own.

**What is in it**

- A command, `attack-test`: `check` (one harmless message, to get a target file right), `list`, `run`, `export` and
  `judge` (for a system with only a chat page), and `practice` (a made-up chatbot).
- A target file per system: where a message goes, where the reply is, and whether the conversation is sent whole
  each time or remembered by the system.
- The core pack: 74 attacks in 8 kinds and 12 ordinary messages, with word lists written for systems that decline
  in their own words (D8).
- An example pack for one system: 44 attacks about that system's own harms, and 20 ordinary messages.
- Judging by word lists, with an optional second model as judge (D9), and each message sent up to five times.
- A report as one HTML page and a JSON file.

**How it was checked**

- 56 tests. They cover what a pack and a target file refuse, that a secret is only ever in a header and never in a
  result, that a redirect is not followed (the key reached no other server), answers that are too large, not JSON
  or not text, a hostile conversation id, the retry when a system is busy, the request limit, giving up after five
  silent messages, the judge (it adds a failure, never clears one, and any odd answer becomes "unsure"), the sheet
  route, and that the page encodes every reply.
- Fourteen attacks have a pinned pair: a refusal that repeats the request must not count, and a reply that gave
  way must.
- A full run of the core pack through the command line against each kind of practice bot. Weak: 36 of 74 gave way
  and 2 ordinary messages were given the planted secret. Holding: 74 held, 12 answered, all 74 marked to read.
  Strict: 74 held, 12 ordinary messages refused.

**What was not checked**

- Any real model or real chat system. The practice bot answers by plain rules.
- A target that streams its answers, needs cookies or sits behind a sign-in page: not supported on this route.
