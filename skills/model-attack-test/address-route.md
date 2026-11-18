# The other way: sending straight to the system's address

Use this when the system has an address that takes a message as JSON and gives back a reply, and no browser is
needed. It is faster, each message gets a conversation of its own, and it can run in a pipeline. The rules in
`SKILL.md` apply here too. `TOOL` is `python3 <full path to scripts/attack-test>`.

One more rule for this route: **never ask for a key, token or password in the chat, and never write one in a
file.** The target file names an environment variable (`${ENV:NAME}`). Tell the person which one to set, and let
them set it.

## 1. Write a target file

Copy the closest file in `scripts/targets/examples/` into the person's project and fill it in:

- `request.url`: https, or http for this computer only. `request.headers`: any key as `${ENV:NAME}`.
- `request.body`: the JSON the system expects, with `"{{messages}}"` where the whole conversation goes, or
  `{{message}}` and `{{session}}` when the system remembers the conversation itself.
- `reply`: where the assistant's words are in the answer, as a dotted path (`choices.0.message.content`).
- `refusals`: the system's set refusal sentence. `never_say`: a phrase that must never come out.
- `skip`: for a general assistant, `off topic`, `persona and style` and `markup and links`.

Every field is explained at the top of `scripts/attack_test/target.py`.

## 2. Check it

```bash
python3 TOOL check --target their-target.json
```

It sends one harmless message. Keep fixing the file until what comes back is the assistant's reply and nothing else.

## 3. Run

```bash
python3 TOOL list --pack core --pack recent
```

Tell the person how many messages that is and get their go-ahead. Then:

```bash
python3 TOOL run --target their-target.json --pack core --pack recent --yes
```

- `--pack their-pack.json` adds a pack written for their system.
- `--repeat 3` sends each message three times. A model's answers vary, and once is enough for an attacker.
- `--judge judge-target.json` has a second model read every reply. Only a model the person is allowed to send the
  system's replies to.
- `--variants base64,reversed,story` also sends each attack in those disguises (see "Going further" in `SKILL.md`).
- `--attacker attacker-target.json` has a model write its own messages towards the packs' open goals, up to
  `--turns` messages each. The goals are harmless on purpose. The system's replies are sent to that model, so use
  one the person is allowed to send them to. If that model declines the job, the goal is marked as not tried.
- `--pack cost` adds the attacks on what the system costs to run: requests for endless replies, three very large
  messages (the largest about 85 pages) and one burst of thirty requests. It costs more than the other packs, so get
  the person's go-ahead for it on its own, and never make a probe bigger or send it more often.
- `python3 TOOL plant --out PLANTS` makes planted documents, and `python3 TOOL compare OLDER NEWER` says what
  changed between two runs. Both are described in `SKILL.md`.
- Never add `--production` unless the person says, in their own words, that production is what they mean.

## 4. Read and report

As in steps 6 and 7 of `SKILL.md`: read `results.json` in the report folder, every reply under "Gave way",
"Ordinary messages refused" and "Held, to read" and "Ordinary messages to read", and tell the person plainly.
