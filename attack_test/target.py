"""The target: the file that says how to reach a chat system, and the one place that sends anything to it.

A target file is JSON:

  name          what the system is called
  owner         who owns it and agreed to this test (a person or a team). Shown on the report
  environment   local, dev, test, staging or production. Production is refused unless asked for by name
  request       how one message is sent:
                  url       https, or http for this computer only. May hold {{session}} in its path
                  method    POST (the default) or PUT
                  headers   name: value. A secret is written ${ENV:NAME} and read from the environment when sent
                  body      any JSON. Inside it:
                              "{{messages}}"  on its own becomes the whole conversation as a list
                              {{message}}     becomes the newest message
                              {{session}}     becomes this conversation's id
  reply         where the assistant's words are in the answer, as a dotted path (choices.0.message.content).
                Left empty, the whole answer is taken as the reply
  conversation  style "messages": every request carries the whole conversation (the default)
                style "session":  the system remembers, and each request carries only the newest message.
                                  "start" may hold a request that opens a conversation and "session", the path to
                                  its id in the answer. Without "start" a random id is made here
                roles, role_key, content_key, prefix: how each message in the list is written, and messages that go
                first every time (a system prompt, when the target is a bare model)
  refusals      word lists that show the assistant declined (its fixed sentence, if it has one)
  never_say     word lists that must never appear in any reply (phrases from its instructions, a made-up secret)
  skip          categories or ids to leave out for this system
  limits        seconds_between (a pause between requests), timeout (seconds to wait for an answer), long_reply
                (how many characters is too long a reply for this system, in place of what each cost attack allows)

Secrets are only ever read from the environment, only ever put in a header, and never written to a result.
"""
from __future__ import annotations

import json
import os
import re
import secrets as random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import Problem
from .packs import patterns, read_json

LOCAL = {"localhost", "127.0.0.1", "::1"}
ENVIRONMENTS = ("local", "dev", "test", "staging", "production")
SECRET = re.compile(r"\$\{ENV:([A-Z][A-Z0-9_]{0,63})\}")
HEADER = re.compile(r"^[A-Za-z0-9-]{1,64}$")
PATH = re.compile(r"^[A-Za-z0-9_.-]{0,200}$")
SESSION = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
SLOT = re.compile(r"\{\{(message|session)\}\}")
MAX_ANSWER = 1_000_000     # bytes read from one answer
MAX_REPLY = 20_000         # characters of a reply that are kept and judged
RETRY_ON = (429, 503)


class Failure(Exception):
    """A request that did not give a usable reply. `detail` is a little of what came back, for `check` only. `kind`
    says why: "status" (the system answered with an error, and `status` is which), "timeout", "unreachable", or
    "other". A test of the system's limits needs to tell a refusal from a system that fell over."""

    def __init__(self, message: str, detail: str = "", kind: str = "other", status: int = 0):
        super().__init__(message)
        self.detail, self.kind, self.status = detail, kind, status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is never followed: it would carry the key in the headers to wherever the answer pointed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _string(value, what: str, limit: int, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Problem(f"Target file: {what} must be text of 1 to {limit} characters.")
    return value.strip()


def _number(value, what: str, low: float, high: float, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise Problem(f"Target file: {what} must be a number from {low:g} to {high:g}.")
    return float(value)


def _path(value, what: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or not PATH.match(value):
        raise Problem(f"Target file: {what} must be a dotted path such as choices.0.message.content.")
    return value


def _contains(node, word: str) -> bool:
    if isinstance(node, str):
        return word in node
    if isinstance(node, list):
        return any(_contains(x, word) for x in node)
    if isinstance(node, dict):
        return any(_contains(v, word) for v in node.values())
    return False


def _request(raw, what: str) -> dict:
    """One request as the target file writes it, checked. The address is the part that matters most: it decides
    where a run of hostile-looking messages and a key are sent."""
    if not isinstance(raw, dict):
        raise Problem(f"Target file: {what} must be an object with a url.")
    extra = sorted(set(raw) - {"url", "method", "headers", "body"})
    if extra:
        raise Problem(f"Target file: {what} has a field this tool does not know: {extra[0]!r}.")
    url = _string(raw.get("url"), f"{what}.url", 2000)
    if "{{message}}" in url or "{{messages}}" in url or SECRET.search(url):
        raise Problem(f"Target file: {what}.url must not hold a message or a secret. Put them in the body or a header.")
    try:
        parts = urllib.parse.urlsplit(url)
        host, port = parts.hostname or "", parts.port
    except ValueError:
        raise Problem(f"Target file: {what}.url is not a valid address.") from None
    if parts.username or parts.password or "@" in parts.netloc:
        raise Problem(f"Target file: {what}.url must not hold a user name or password.")
    if not host or "{" in parts.netloc:
        raise Problem(f"Target file: {what}.url needs a host name, written out in full.")
    if parts.scheme != "https" and not (parts.scheme == "http" and host in LOCAL):
        raise Problem(f"Target file: {what}.url must be https. Plain http is allowed for this computer only (localhost).")
    method = raw.get("method", "POST")
    if method not in ("POST", "PUT"):
        raise Problem(f"Target file: {what}.method must be POST or PUT.")
    headers = raw.get("headers", {})
    if not isinstance(headers, dict) or len(headers) > 30:
        raise Problem(f"Target file: {what}.headers must be an object of at most 30 headers.")
    for name, value in headers.items():
        if not HEADER.match(name) or not isinstance(value, str) or len(value) > 2000 or "\r" in value or "\n" in value:
            raise Problem(f"Target file: {what}.headers has a name or value that is not allowed ({name!r}).")
    body = raw.get("body", {})
    if _contains(body, "${ENV:"):
        raise Problem(f"Target file: {what}.body must not hold a secret. A secret goes in a header.")
    return {"url": url, "host": host, "port": port, "local": host in LOCAL, "method": method, "headers": dict(headers), "body": body}


def load(path: str) -> dict:
    """A target file, checked. Raises Problem with a plain sentence if anything is not as it should be."""
    raw = read_json(Path(path).expanduser(), "target file")
    if not isinstance(raw, dict):
        raise Problem("Target file: the file must hold one object.")
    known = {"name", "owner", "environment", "request", "reply", "conversation", "refusals", "never_say", "skip", "limits"}
    extra = sorted(set(raw) - known)
    if extra:
        raise Problem(f"Target file: there is a field this tool does not know: {extra[0]!r}.")
    environment = raw.get("environment")
    if environment not in ENVIRONMENTS:
        raise Problem(f"Target file: environment must be one of: {', '.join(ENVIRONMENTS)}.")
    request = _request(raw.get("request"), "request")
    conv = raw.get("conversation", {})
    if not isinstance(conv, dict) or set(conv) - {"style", "roles", "role_key", "content_key", "prefix", "start", "session"}:
        raise Problem("Target file: conversation may hold style, roles, role_key, content_key, prefix, start and session.")
    style = conv.get("style", "messages")
    if style not in ("messages", "session"):
        raise Problem('Target file: conversation.style must be "messages" or "session".')
    roles = conv.get("roles", {})
    if not isinstance(roles, dict) or set(roles) - {"user", "assistant"}:
        raise Problem("Target file: conversation.roles may name what the system calls the user and the assistant.")
    prefix = conv.get("prefix", [])
    if not isinstance(prefix, list) or len(prefix) > 20 or not all(isinstance(m, dict) for m in prefix):
        raise Problem("Target file: conversation.prefix must be a list of at most 20 messages.")
    start = _request(conv["start"], "conversation.start") if conv.get("start") is not None else None
    if start and (start["host"], start["port"]) != (request["host"], request["port"]):
        raise Problem("Target file: conversation.start must go to the same host as the request.")
    if style == "messages" and (start or _contains(request["body"], "{{session}}") or "{{session}}" in request["url"]):
        raise Problem('Target file: {{session}} and conversation.start belong to the style "session".')
    if style == "session" and _contains(request["body"], "{{messages}}"):
        raise Problem('Target file: {{messages}} belongs to the style "messages".')
    if not _contains(request["body"], "{{message}}") and not _contains(request["body"], "{{messages}}"):
        raise Problem("Target file: request.body must hold {{message}} or {{messages}}, or nothing would be sent.")
    limits = raw.get("limits", {})
    if not isinstance(limits, dict) or set(limits) - {"seconds_between", "timeout", "long_reply"}:
        raise Problem("Target file: limits may hold seconds_between, timeout and long_reply.")
    skip = raw.get("skip", [])
    if not isinstance(skip, list) or len(skip) > 200 or not all(isinstance(x, str) and 0 < len(x) <= 80 for x in skip):
        raise Problem("Target file: skip must be a list of categories or ids.")
    return {
        "name": _string(raw.get("name"), "name", 80),
        "owner": _string(raw.get("owner"), "owner (who owns the system and agreed to this test)", 120),
        "environment": environment,
        "request": request,
        "reply": _path(raw.get("reply"), "reply"),
        "style": style,
        "roles": {"user": _string(roles.get("user", "user"), "conversation.roles.user", 40),
                  "assistant": _string(roles.get("assistant", "assistant"), "conversation.roles.assistant", 40)},
        "role_key": _string(conv.get("role_key", "role"), "conversation.role_key", 40),
        "content_key": _string(conv.get("content_key", "content"), "conversation.content_key", 40),
        "prefix": prefix,
        "start": start,
        "session_path": _path(conv.get("session"), "conversation.session"),
        "refusals": patterns(raw.get("refusals"), "Target file: refusals"),
        "never_say": patterns(raw.get("never_say"), "Target file: never_say"),
        "skip": list(skip),
        "seconds_between": _number(limits.get("seconds_between"), "limits.seconds_between", 0, 60, 0.0 if request["local"] else 0.5),
        "timeout": _number(limits.get("timeout"), "limits.timeout", 1, 300, 60.0),
        "long_reply": int(_number(limits.get("long_reply"), "limits.long_reply", 500, MAX_REPLY, 0)),
    }


def needed_secrets(target: dict) -> list[str]:
    """The environment variables this target file asks for, so a run can say which are missing before it starts."""
    requests = [target["request"]] + ([target["start"]] if target["start"] else [])
    return sorted({name for r in requests for v in r["headers"].values() for name in SECRET.findall(v)})


def fill(node, message: str, session: str, messages: list | None):
    """The body with its slots filled. A slot inside a message that was itself filled in is left alone, so an attack
    that contains {{session}} arrives as it was written."""
    if isinstance(node, str):
        if node == "{{messages}}" and messages is not None:
            return messages
        return SLOT.sub(lambda m: message if m.group(1) == "message" else session, node)
    if isinstance(node, list):
        return [fill(x, message, session, messages) for x in node]
    if isinstance(node, dict):
        return {k: fill(v, message, session, messages) for k, v in node.items()}
    return node


def extract(data, path: str):
    """What is at a dotted path in an answer. A number steps into a list."""
    for step in [p for p in path.split(".") if p]:
        if isinstance(data, list) and step.isdigit() and int(step) < len(data):
            data = data[int(step)]
        elif isinstance(data, dict) and step in data:
            data = data[step]
        else:
            raise Failure(f"the answer had nothing at {path!r}")
    return data


class Sender:
    """Sends messages to one target. Everything that leaves this tool for a target goes through `_send`."""

    def __init__(self, target: dict, env=None, sleep=time.sleep, retry_wait: float = 10.0):
        self.target, self.env, self.sleep, self.retry_wait = target, os.environ if env is None else env, sleep, retry_wait
        missing = [n for n in needed_secrets(target) if not self.env.get(n)]
        if missing:
            raise Problem(f"Set the environment variable {missing[0]} first. The target file reads a secret from it.")
        handlers = [_NoRedirect()]
        if target["request"]["local"]:
            handlers.append(urllib.request.ProxyHandler({}))   # this computer is never reached through a proxy
        self.opener = urllib.request.build_opener(*handlers)
        self.requests = 0
        self.last_chars = 0
        self._sent_before = False

    def _send(self, request: dict, message: str, session: str, messages: list | None, patient: bool = True) -> str:
        url = request["url"].replace("{{session}}", urllib.parse.quote(session, safe=""))
        body = json.dumps(fill(request["body"], message, session, messages), ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "model-attack-test"}
        headers.update({k: SECRET.sub(lambda m: self.env[m.group(1)], v) for k, v in request["headers"].items()})
        for attempt in (1, 2):
            if self._sent_before and self.target["seconds_between"] and patient:
                self.sleep(self.target["seconds_between"])
            self._sent_before = True
            self.requests += 1
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method=request["method"])
                with self.opener.open(req, timeout=self.target["timeout"]) as answer:
                    raw = answer.read(MAX_ANSWER + 1)
                if len(raw) > MAX_ANSWER:
                    raise Failure("the answer was larger than 1 MB")
                return raw.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read(600).decode("utf-8", errors="replace")
                except OSError:
                    detail = ""
                finally:
                    e.close()
                if e.code in RETRY_ON and attempt == 1 and patient:
                    self.sleep(self.retry_wait)   # told to slow down, or busy: wait once and try again
                    continue
                if 300 <= e.code < 400:
                    raise Failure(f"the system answered with a redirect (status {e.code}), which is never followed") from None
                raise Failure(f"the system answered with status {e.code}", detail, "status", e.code) from None
            except (socket.timeout, TimeoutError):
                raise Failure(f"no answer within {self.target['timeout']:g} seconds", kind="timeout") from None
            except urllib.error.URLError as e:
                if isinstance(e.reason, (socket.timeout, TimeoutError)):
                    raise Failure(f"no answer within {self.target['timeout']:g} seconds", kind="timeout") from None
                raise Failure(f"could not reach {request['host']}", kind="unreachable") from None
            except (OSError, ValueError):
                raise Failure(f"could not reach {request['host']}", kind="unreachable") from None
        raise Failure("the system kept answering that it was busy")

    def _reply(self, text: str) -> str:
        """The assistant's words out of an answer. Whatever comes back is treated as hostile: it must be text, and
        only so much of it is kept."""
        if not self.target["reply"]:
            self.last_chars = len(text)
            return text[:MAX_REPLY]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise Failure("the answer was not JSON", text[:600]) from None
        try:
            value = extract(data, self.target["reply"])
        except Failure as e:
            raise Failure(str(e), text[:600]) from None
        if not isinstance(value, str):
            raise Failure(f"what was at {self.target['reply']!r} in the answer was not text", text[:600])
        self.last_chars = len(value)   # how long the reply really was, before only so much of it is kept
        return value[:MAX_REPLY]

    def _open(self) -> str:
        """A fresh conversation's id: from the system when the target file says how to ask, otherwise made here."""
        t = self.target
        if not t["start"]:
            return random.token_hex(16)
        text = self._send(t["start"], "", "", None)
        try:
            value = extract(json.loads(text), t["session_path"])
        except json.JSONDecodeError:
            raise Failure("the answer that should open a conversation was not JSON", text[:600]) from None
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str) or not SESSION.match(value):
            raise Failure("the conversation id the system gave back was not one this tool will use")
        return value

    def start(self) -> dict:
        """A fresh conversation, to be carried on with `say`."""
        return {"session": self._open() if self.target["style"] == "session" else "", "messages": list(self.target["prefix"])}

    def say(self, conversation: dict, said: str, patient: bool = True) -> str:
        """One more message in a conversation, and the reply to it. The system's own replies are what it is shown of
        its side: nothing is put in its mouth. Without `patient` there is no pause before it and no second try when the
        system says it is busy: that is for seeing whether the system limits how fast it can be sent to."""
        t, messages = self.target, conversation["messages"]
        messages.append({t["role_key"]: t["roles"]["user"], t["content_key"]: said})
        reply = self._reply(self._send(t["request"], said, conversation["session"], messages if t["style"] == "messages" else None, patient))
        messages.append({t["role_key"]: t["roles"]["assistant"], t["content_key"]: reply})
        return reply

    def converse(self, earlier: list[str], text: str) -> tuple[str, list[str]]:
        """One fresh conversation: each earlier message in turn, then the message itself. Returns the reply to the
        message, and the replies the earlier ones got."""
        conversation = self.start()
        replies = [self.say(conversation, said) for said in [*earlier, text]]
        return replies[-1], replies[:-1]
