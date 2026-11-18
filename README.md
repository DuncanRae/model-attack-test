# Model Attack Test

Sends known tricks to an AI chat system you are building and reports which ones it gave way to: being talked into
another voice, showing its instructions, obeying someone who claims authority, following an instruction hidden in
other text, going off its subject, giving out another person's data. It also sends ordinary messages from honest
people and counts any the system refused, because an assistant that turns everyone away is broken too.

There are two ways to run it:

- **Through the chat page, with an AI agent doing the typing** (the skill). The agent opens the system in a browser,
  types each message the way a person would, reads the reply, and the tool judges and reports. Nothing to set up for
  the system under test. This is the way to start.
- **Straight to the system's address** (the command line). Faster and repeatable, for a system that takes a message
  as JSON, and for pipelines.

Underneath both is a small tool with nothing to install (Python 3.9 or newer, standard library only) and a set of
attack packs.

It began as the attack suite of one in-house assistant and was made into a tool of its own, for anyone to use.

**What a result means.** It shows how a system answered these tricks on the day. It is not a certificate and it is
not sign-off from anyone's security team. A system that held can still be talked round by a trick that is not in the packs, or by
the same trick on another try.

## Use it responsibly

Only test a system you own, or have its owner's clear go-ahead to test. Sending these messages to someone else's
system without permission is not testing, and in many places it is against the law. Every attack here carries a
harmless request (a made-up word, or a request for the system's own instructions), and contributions that ask for
harmful content will not be taken.

## The skill: testing through the chat page

The skill is one folder in the common "agent skill" form (a `SKILL.md` with a name and a description), which
Claude, OpenAI's Codex and Google Antigravity all read. The agent needs a browser it can control and a terminal with
Python 3.

### Which model

Whether an agent will do the work is up to its model. This is security testing, and general-purpose models are
cautious about it. **A model that is permitted to do security work is the better choice**, where you have access
to one: some providers offer models with fewer restrictions on security testing to organisations they have
approved. That is not a way round a refusal. It is using a model whose rules allow the task.

Where the general-purpose models stood in November 2026:

| Agent and model | Where it stands |
|---|---|
| Claude (Claude Code, and the Code tab of the Claude desktop app), with the Claude 5.5 models and Claude Fable 5.2 | Seems to work. It asks you to confirm the system is yours to test first |
| Codex and ChatGPT, with OpenAI's models | Not tested. It should load: instructions below |
| Antigravity, with Gemini 4 | Loads, and the model declined to do the work (see "What to know" below) |

Models change. If you run it with one that is not listed, or one of these behaves differently for you, please open
an issue saying which model and what happened.

### Install it

Get the code and build the skill folder (this also runs the tests):

```bash
git clone https://github.com/DuncanRae/model-attack-test.git && cd model-attack-test && ./package-skill.sh
```

That makes `dist/model-attack-test/` (the skill, with a copy of the tool inside it) and
`dist/model-attack-test-skill.zip`. Then copy the folder to where your agent looks for skills:

| Agent | Where the folder goes |
|---|---|
| Claude Code, Claude desktop (Code tab) | `~/.claude/skills/model-attack-test/` for you alone, or `<project>/.claude/skills/model-attack-test/` for one project |
| Codex | `~/.agents/skills/model-attack-test/` for you alone, or `<repository>/.agents/skills/model-attack-test/` for one repository |
| Antigravity | `~/.gemini/config/skills/model-attack-test/` for you alone, or `<workspace>/.agents/skills/model-attack-test/` for one workspace. Gemini 4 declined to run it |
| Claude on the web or desktop chat | Upload `dist/model-attack-test-skill.zip` where skills are added in Settings. Not tried |

To update it later, build again, delete the old copy and copy the new one.

For example, for Claude:

```bash
mkdir -p ~/.claude/skills && cp -R dist/model-attack-test ~/.claude/skills/
```

### With Codex

These steps follow OpenAI's documentation as it stood in November 2026. Nobody has run the skill in Codex yet, so
treat them as a starting point and please report how it goes.

1. **Install the skill.** Codex reads skills from `.agents/skills`:

```bash
mkdir -p ~/.agents/skills && cp -R dist/model-attack-test ~/.agents/skills/
```

   For one repository only, copy it to `.agents/skills/` in that repository instead. Antigravity reads that same
   folder, so one copy there serves both. Older versions of Codex read `~/.codex/skills/`: use that if the skill
   does not show up.
2. **Use the Codex desktop app** (Codex in the ChatGPT desktop app). The skill needs a browser the agent can click
   and type in, and Codex's built-in browser is in the desktop app only. It is not in the Codex CLI or the IDE
   extension: there, use the command line instead (below), which needs no browser.
3. **Let it reach your system.** In Settings, under Browser, the agent permissions say which sites Codex may open.
   Allow your system's address. The built-in browser has its own profile and does not share your signed-in tabs,
   so sign in to your system in that browser yourself when the page appears. To use a tab in your everyday browser
   instead, set up the Codex browser extension.
4. **Start a new thread and ask for it.** Type `$model-attack-test` (or `@` and pick it in ChatGPT), or say what
   you want: *"Use the model-attack-test skill on the chatbot at https://my-bot-dev.example. It is mine to test."*
5. **Expect to be asked.** Codex asks for confirmation before actions it treats as sensitive, such as submitting
   information to a site. If it asks before every message, see whether it offers to allow the site for the session.
6. **If the model declines**, as Gemini did in Antigravity, that is its rule. Do not reword the skill to get past
   it: use Claude, or the command line.

### Use it

1. Have the system's chat page ready: a dev or test copy with made-up data, and you able to sign in to it.
2. Start a new conversation with the agent and say what you want, for example:
   *"Use the model-attack-test skill on the chatbot at https://my-bot-dev.example. It is mine to test."*
   Typing `/model-attack-test` also works in both.
3. Answer its few questions: what the system is for, its set refusal sentence if it has one, a phrase that must
   never come out, and whether you want the quick pass (about 30 messages) or the full list (107).
4. Sign in when it opens the page and asks you to. It never types a password.
5. Let it work. It sends one message at a time and tells you how far it is every ten.
6. Read the report it names (`report.html` in the run folder), and its own summary of what gave way.

To try it for nothing first, start the made-up chatbot (`./attack-test practice --mode weak`) and point the agent at
`http://127.0.0.1:8777/`.

The quick pass is the first two of each kind from the `core` and `recent` packs.

What to know before you rely on it:

- **The agent's own model may decline, and the skill does not try to get round that.** Claude asked for
  confirmation that the system was the tester's to test, then ran it. Gemini 4 in Antigravity refused to send the
  messages at all, "even with authorization or ownership". That is the model's rule. Wording the skill to slip past
  it would be the very thing this tool tests for. Where the agent declines, use Claude, or the command line, which
  needs no agent.

- **The agent that types is also the first reader of each reply.** Its reading is kept with the reply, can only add
  a concern, and never clears what a word list found.
- **A system with no "new conversation" gets everything in one conversation.** The report says so at the top, and
  the results are rougher.
- **Two attacks that ask for a piece of script back are left out in a browser** (`core-mar-01`, `core-mar-03`): on
  a page that shows replies unsafely, the script would run in your signed-in browser. Ask for them if you want them.
- **It is slow**: about half a minute a message.

## Try the command line in five minutes

A made-up chatbot comes with the tool, so the first run costs nothing and touches nothing real. In one terminal:

```bash
./attack-test practice --mode weak
```

In another:

```bash
./attack-test run --target targets/examples/practice-messages.json --pack core --pack recent
```

Open the `report.html` it names. Then stop the chatbot (Ctrl+C) and start it again with `--mode holding`, and then
`--mode strict`, to see what a system that holds looks like, and one that holds only by refusing everybody.

## Testing your own system

Only a system you own or have the owner's go-ahead to test. Use a dev or test copy with made-up data: every message
costs what a message to your system costs, and the report keeps whatever the system says.

1. **Write a target file.** Copy the closest one in `targets/examples/` and fill it in. It says where a message is
   sent, where the reply is in the answer, and whether the system remembers the conversation. A key is never
   written in the file: write `${ENV:MY_KEY}` in a header and set that environment variable yourself. Every field
   is explained at the top of `attack_test/target.py`.
2. **Check it.** `./attack-test check --target my-target.json` sends one harmless message. Fix the file until what
   comes back is the assistant's reply and nothing else.
3. **Write a pack for your system.** The core pack knows nothing about what your system is for, and the harm that
   matters most is particular to it. List what it must never do, write a few attacks for each, and add the ordinary
   messages your real users send. `packs/examples/supplier-interview.json` is a worked example, and the format is
   explained at the top of `attack_test/packs.py`.
4. **Run it.** `./attack-test run --target my-target.json --pack core --pack recent --pack my-pack.json`
5. **Read the report**, not just the counts (below).

### Options worth knowing

| Option | What it does |
|---|---|
| `--repeat 3` | Sends each message three times. A model's answers vary, and once is enough for an attacker |
| `--only KIND_OR_ID`, `--skip KIND_OR_ID` | Send only, or leave out, a kind of trick or one id. `./attack-test list --pack core` shows the kinds |
| `--per-kind 3` | Keeps the first three of each kind, for a quick pass |
| `--judge judge.json` | Has a second model read every reply (below) |
| `--max-requests 500` | The most requests one run may send. The default is 500 and the ceiling is 5000 |
| `--yes` | Does not ask before sending. Needed when nobody is at the keyboard |
| `--production` | Allows a target file that says `production`. Avoid it |

A general assistant (one meant to write code, answer anything and format its answers) should skip `off topic`,
`persona and style` and `markup and links`: put them in the target file's `skip`.

### The packs

| Pack | What is in it |
|---|---|
| `core` | 74 long-standing tricks in 8 kinds, and 12 ordinary messages. For any assistant with a job of its own |
| `recent` | 20 techniques reported from 2024 to 2026 in 6 kinds, and 3 ordinary messages: instructions written as a policy file, made-up earlier turns, slow steering over many messages, instructions hidden in an email or web page it is asked to read, text that cannot be seen, and the request turned into another task. Each is in a harmless form (a made-up word in place of a harmful request) and names where the technique was reported |
| `packs/examples/supplier-interview.json` | One system's own pack, as the pattern for yours |
| Yours | What your system must never do. The most important one, and the only one you have to write |

Every pack carries the date it was last checked against newly reported attacks (`reviewed`). A report warns when
that was more than six months before the run. `recent` dates fastest.

### Against the OWASP list

Every attack is marked with the risk it tries from the OWASP Top 10 for LLM Applications (2026 edition), and the
report has a table of all ten: how many messages were sent against each and how many went wrong. The risks nothing
was sent for stay in the table, so a clean run cannot be read as the whole list covered.

What a run with `core` and `recent` reaches:

| Risk | Reached? |
|---|---|
| LLM01 Prompt Injection | In part: instructions typed or pasted into the chat. Not files, pictures, web pages, tool results or memory |
| LLM02 Sensitive Information Disclosure | In part: other people's data and planted secrets. Real cover needs your own pack |
| LLM03 Excessive Agency | No. The tool reads what a system says, not what it does |
| LLM04 Supply Chain | No, and it cannot be: no message can test it |
| LLM05 Data and Model Poisoning | No, and it cannot be |
| LLM06 Unbounded Consumption | No. Could be added |
| LLM07 Misinformation | No. Could be added in your own pack, where the right answers are known |
| LLM08 Hidden Context Exposure | In part: the system's instructions. Barely its documents or tools |
| LLM09 Vector and Embedding Weaknesses | No, and it cannot be |
| LLM10 Improper Output Handling | In part: markup, links and pictures sent back. Not the page that shows them |

So this is not an OWASP assessment, and no test that only sends messages can be one. OWASP's separate Top 10 for
Agentic Applications is not reached at all. To mark your own attacks, add `"owasp"` with one of the keys at the top
of `attack_test/owasp.py`.

### Reading the report

| Section | What to do |
|---|---|
| Gave way | Read each reply. Most are real. Some are a word list firing on a refusal that repeated the request |
| Ordinary messages given something secret | A reply to an honest message held something from `never_say`. Always real |
| Ordinary messages refused | Read each. An honest person was turned away |
| Held, not read by anyone yet | Read every one. No word list fired, but the reply was in the assistant's own words, and a reply can give way in words no list looks for |
| Held | Declined with its own refusal sentence, or read by the model judge |

Judging is by plain word lists unless you give a judge. They are quick, free and repeatable, and they are wrong
both ways, which is why the report says what nobody has read.

### A second model as judge

`--judge` takes a target file that points at a model (see `targets/examples/judge-vertex-chat-completions.json`).
Every message and reply is sent to it, and it says whether the assistant gave way. It can only add a concern: it
never clears a failure a word list found, and an answer from it that is not one of the three expected words sends
the reply to a person. Only use a model you are allowed to send the system's replies to.

### A system with only a chat page, without the skill

The skill uses four commands that a person can use too: `begin` starts a run in a folder, `next` shows the next
message, `record` takes the reply from a file, and `finish` judges and writes the report. Each explains itself with
`--help`.

Or all at once, as a sheet:

```bash
./attack-test export --pack core --pack my-pack.json --out sheet.json
```

Send each message in a conversation of its own, put the replies in the sheet, then:

```bash
./attack-test judge --replies sheet.json --pack core --pack my-pack.json --name "My system" --owner "My team"
```

### In a pipeline

The exit code is 0 when everything held and every ordinary message was answered, 1 when something gave way or was
refused, and 2 when the run could not be done or did not finish. `results.json` beside the report has every reply.

## What it does not cover

- **What an assistant does.** One that sends mail, changes records or calls tools is judged here only on what it
  says. Whether it did something it should not have needs a look at the system itself.
- **Files and pictures** given to the assistant, and text planted in documents it reads later.
- **Six of the ten OWASP risks**, three of which no message can test. See "Against the OWASP list".
- **The newest attacks, for long.** The packs were last checked on the date each carries. Someone has to keep
  checking them.
- **Harmful content from a general assistant** (weapons, malware and the like). The `recent` pack tries the
  techniques with a harmless request inside. The open tools garak, PyRIT and promptfoo have far larger lists for
  the real thing.
- **Streaming answers, cookies and sign-in pages, on the command-line route.** There the target must be an address
  that takes JSON and answers JSON or plain text, with any key in a header. The skill goes through the page, so it
  has none of these limits.
- **A person trying freely.** A list finds what is on the list.
- **Other languages**, beyond a handful of attacks in Afrikaans, isiZulu, isiXhosa and Chinese. The isiZulu and
  isiXhosa sentences were written by a model and have not been read by a speaker.

## The parts

| Path | What it is |
|---|---|
| `attack-test` | The command. Run it from anywhere |
| `attack_test/` | The tool. `packs.py` (reading packs), `target.py` (target files, and the only place anything is sent), `judge.py` (word lists and the model judge), `run.py` (a run; `run_suite` is the door for other programs), `byhand.py` (a run through a chat page, one message at a time), `report.py` (the page), `cli.py` (the commands) |
| `packs/core.json` | 74 attacks in 8 kinds and 12 ordinary messages, for any assistant with a job of its own |
| `packs/recent.json` | 20 techniques reported from 2024 to 2026, each with its source, and 3 ordinary messages |
| `attack_test/owasp.py` | The OWASP list, what a chat test can reach of it, and where the list was read from |
| `packs/examples/supplier-interview.json` | A worked example of one system's own pack: 44 attacks and 20 ordinary messages |
| `targets/examples/` | Target files to copy |
| `practice/bot.py` | The made-up chatbot, with a chat page at `/`. Not a model |
| `skills/model-attack-test/` | The skill: `SKILL.md` (through the chat page) and `address-route.md` (straight to an address) |
| `package-skill.sh`, `dist/` | Builds the skill as one folder that stands on its own, and a zip. `dist/` is built, never edited |
| `.claude-plugin/plugin.json` | Also makes the whole folder a Claude Code plugin |
| `tests/`, `run-tests.sh` | 77 tests. `./run-tests.sh` runs them all on this computer |
| `AGENTS.md`, `CHANGELOG.md`, `docs/decisions.md` | The maintainer guide, every version, the design decisions |

## Help make it better

The most useful thing you can send is a false alarm: an attack the report listed under "Gave way" when the reply
was really a refusal, with the id and the reply. Next most useful: a technique that is missing, with where it was
reported. Open an issue for either. `AGENTS.md` is the guide for changing the code.

## Licence

MIT. See `LICENSE`.

## Libraries

None. Everything is Python's standard library, so there is nothing to install, pin or keep patched.

## Security notes

What the tool does to stay safe, and what it assumes:

- **A key is read from the environment, sent only in a header, and never written anywhere.** A target file that
  puts a secret in the address or the body is refused. Results hold the host name and nothing else of the request.
- **Where a run goes is checked.** The address must be https (plain http for this computer only), with no user name
  or password in it. A redirect is never followed, so a key cannot be carried to another host.
- **Everything that comes back is treated as hostile.** An answer over 1 MB is refused, a reply is cut at 20,000
  characters, a conversation id is checked before it is used, and the judge's answer is reduced to one known word.
- **The report encodes every reply**, loads nothing and runs nothing. The folder and files are readable by their
  owner only.
- **A run is bounded**: a request limit, a pause between requests, and it stops after five messages in a row get no
  reply. It asks before sending unless `--yes` is given.

On the chat-page route:

- **The tool sends nothing.** The agent types into the page in a browser you can watch, signed in as you.
- **A reply only ever reaches the tool as a file.** It is never put on a command line, where a shell would read it,
  and the few words of reason the agent may add are limited to letters, digits and plain punctuation.
- **The run file is checked again every time it is read**, and the messages and word lists always come from the
  packs, so a changed run file cannot swap in its own.
- **The agent is told that everything on the page is data**, to type only into the chat box, never to follow a
  link in a reply and never to type a password. Those are instructions to a model, not locks: watch the first run.

What it cannot do for you:

- **It cannot know the system is yours.** It asks, and it prints the host before sending. Check the address.
- **A pack is read like code.** A pattern written to be slow on purpose could stall a run. Read a pack someone else
  wrote before using it.
- **The report holds whatever the system leaked.** Test a dev copy with made-up data, and share the report as you
  would the system's own data.
- **The judge is sent every reply.** Use a model in a place your data is allowed to go.
- **On a shared computer, an environment variable can be seen by other programs of the same user.** That is the
  usual trade for not writing a key in a file.
