"""The OWASP Top 10 for LLM Applications, and what a run can honestly say against each risk.

An attack in a pack may carry `"owasp": "<key>"`, one of the keys below. The key is a name, not a number, because
OWASP renumbers the list between editions: the 2026 edition moved six of the ten and renamed one.

Where this list came from, so it can be checked: OWASP GenAI Security Project, "OWASP GenAI LLM Top 10 2026", v1.0,
3 August 2026 (genai.owasp.org/resource/owasp-genai-llm-top-10-2026/). That page offers the document as a download
only, so the ten titles and their order here were read on 18 November 2026 from two write-ups that agree with each
other (Invicti, and the Cloud Security Alliance research note). The 2025 numbers are from OWASP's own page
(genai.owasp.org/llm-top-10/), which still showed the 2025 edition on that day. If a title here is wrong, this file
is the one place to put it right.

`reach` is what sending messages to a chat system can do about a risk, whatever is in the packs:
  yes    messages can try it
  words  messages can try to bring it about, but this tool only sees what the system SAYS, not what it does
  no     it is about how the system was built or what it was trained on: no message can test it
"""
from __future__ import annotations

EDITION = "OWASP Top 10 for LLM Applications 2026"
EDITION_DETAIL = "v1.0, 3 August 2026"

RISKS = [
    {"key": "prompt-injection", "id": "LLM01", "title": "Prompt Injection", "was": "LLM01:2025", "reach": "yes",
     "note": "Reaches instructions typed or pasted into the chat, and, when planted documents are used, instructions in files the system reads. Does not reach pictures, web pages it fetches, tool results or memory."},
    {"key": "sensitive-information", "id": "LLM02", "title": "Sensitive Information Disclosure", "was": "LLM02:2025", "reach": "yes",
     "note": "Reaches asking for other people's data, and anything named in never_say. Real cover needs a pack written for this system's own data."},
    {"key": "excessive-agency", "id": "LLM03", "title": "Excessive Agency", "was": "LLM06:2025", "reach": "words",
     "note": "Not tested. This tool reads what a system says. Whether it sent, changed or deleted something it should not have needs a look at the system itself."},
    {"key": "supply-chain", "id": "LLM04", "title": "Supply Chain", "was": "LLM03:2025", "reach": "no",
     "note": "Cannot be tested by sending messages. It needs a review of the models, libraries and tools the system is built from."},
    {"key": "poisoning", "id": "LLM05", "title": "Data and Model Poisoning", "was": "LLM04:2025", "reach": "no",
     "note": "Cannot be tested by sending messages. It needs a review of what the model was trained and tuned on."},
    {"key": "unbounded-consumption", "id": "LLM06", "title": "Unbounded Consumption", "was": "LLM10:2025", "reach": "yes",
     "note": "Reached only with the cost pack, which is run when asked for: requests for endless output, very large messages and one short burst. "
             "It looks for a missing limit. It does not measure money, and it does not reach a system's tools, its own loops, or many users at once."},
    {"key": "misinformation", "id": "LLM07", "title": "Misinformation", "was": "LLM09:2025", "reach": "yes",
     "note": "Could be tried with questions whose right answer is known for this system. The packs that come with the tool do not check whether an answer is true."},
    {"key": "hidden-context", "id": "LLM08", "title": "Hidden Context Exposure", "was": "LLM07:2025 System Prompt Leakage", "reach": "yes",
     "note": "Reaches the system's instructions and what it has been told to keep back. Barely reaches documents it looks things up in, or how its tools are called."},
    {"key": "vector-embedding", "id": "LLM09", "title": "Vector and Embedding Weaknesses", "was": "LLM08:2025", "reach": "no",
     "note": "Cannot be tested by sending messages. It needs a review of how the system stores and looks up its documents."},
    {"key": "output-handling", "id": "LLM10", "title": "Improper Output Handling", "was": "LLM05:2025", "reach": "yes",
     "note": "Reaches markup, links and pictures sent back in a reply. Whether they do harm depends on the page or program that shows the reply, which is not tested."},
]
KEYS = tuple(r["key"] for r in RISKS)
AGENTIC = ("OWASP's separate Top 10 for Agentic Applications (an assistant that uses tools, keeps a memory, holds an identity or "
           "works with other agents) is not tested by this tool at all.")
READING = ("A risk with messages sent and none gone wrong is not a risk passed. It means these messages did not get through on "
           "this day. A risk with nothing sent is not covered by this run at all.")


def coverage(rows: list[dict]) -> dict:
    """What a run sent against each risk and how it went, with the risks it could not or did not touch left in."""
    out = []
    for risk in RISKS:
        mine = [r for r in rows if r.get("owasp") == risk["key"]]
        out.append(dict(risk, sent=sum(1 for r in mine if r["verdict"] not in ("error", "not run", "not reached")),
                        went_wrong=sum(1 for r in mine if r["verdict"] in ("failed", "blocked", "leaked")),
                        to_read=sum(1 for r in mine if r.get("read")),
                        no_reply=sum(1 for r in mine if r["verdict"] in ("error", "not run", "not reached"))))
    attacks = [r for r in rows if not r["ordinary"]]
    return {"edition": EDITION, "detail": EDITION_DETAIL, "rows": out, "agentic": AGENTIC, "reading": READING,
            "untagged": sum(1 for r in attacks if not r.get("owasp"))}
