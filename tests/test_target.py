import json
import unittest

from tests.helpers import Servers, no_sleep

from attack_test import Problem, target
from attack_test.target import Failure, Sender

GOOD = {"name": "Bot", "owner": "Me", "environment": "dev",
        "request": {"url": "https://bot.example/chat", "headers": {"Authorization": "Bearer ${ENV:BOT_KEY}"}, "body": {"messages": "{{messages}}"}},
        "reply": "choices.0.message.content"}


class TargetFiles(unittest.TestCase):
    def setUp(self):
        self.s = Servers()
        self.addCleanup(self.s.close)

    def load(self, **changes):
        data = json.loads(json.dumps(GOOD))
        data.update(changes)
        return target.load(self.s.file("t.json", data))

    def refused(self, sentence, **changes):
        with self.assertRaises(Problem) as caught:
            self.load(**changes)
        self.assertIn(sentence, str(caught.exception))

    def test_a_good_file_loads_and_says_which_secrets_it_needs(self):
        t = self.load()
        self.assertEqual((t["request"]["host"], t["style"], t["seconds_between"]), ("bot.example", "messages", 0.5))
        self.assertEqual(target.needed_secrets(t), ["BOT_KEY"])

    def test_where_a_run_may_be_sent(self):
        body = {"messages": "{{messages}}"}
        self.refused("must be https", request={"url": "http://bot.example/chat", "body": body})
        self.refused("must be https", request={"url": "ftp://bot.example/chat", "body": body})
        self.refused("user name or password", request={"url": "https://me:pw@bot.example/chat", "body": body})
        self.refused("must not hold a message or a secret", request={"url": "https://bot.example/chat?q={{message}}", "body": body})
        self.refused("must not hold a message or a secret", request={"url": "https://bot.example/${ENV:KEY}", "body": body})
        self.refused("host name, written out", request={"url": "https://{{session}}.example/chat", "body": body})
        self.refused("POST or PUT", request={"url": "https://bot.example/chat", "method": "DELETE", "body": body})
        self.assertTrue(self.load(request={"url": "http://localhost:8000/chat", "body": body})["request"]["local"])

    def test_a_secret_is_only_ever_in_a_header(self):
        self.refused("A secret goes in a header", request={"url": "https://bot.example/chat", "body": {"key": "${ENV:BOT_KEY}", "messages": "{{messages}}"}})
        self.refused("not allowed", request={"url": "https://bot.example/chat", "headers": {"X-Key": "a\r\nX-Other: b"}, "body": {"messages": "{{messages}}"}})

    def test_the_rest_of_what_is_refused(self):
        self.refused("environment must be one of", environment="prod")
        self.refused("does not know", debug=True)
        self.refused("owner", owner="")
        self.refused("dotted path", reply="choices[0].message")
        self.refused("or nothing would be sent", request={"url": "https://bot.example/chat", "body": {"q": "hello"}})
        self.refused("not a valid regular expression", refusals=["("])
        self.refused('belong to the style "session"', request={"url": "https://bot.example/chat", "body": {"s": "{{session}}", "m": "{{message}}"}})
        self.refused("same host", conversation={"style": "session", "start": {"url": "https://other.example/new", "body": {}}, "session": "id"},
                     request={"url": "https://bot.example/say", "body": {"m": "{{message}}"}})
        self.refused("limits.timeout", limits={"timeout": 0})

    def test_filling_the_body(self):
        body = {"model": "m", "messages": "{{messages}}", "note": "last: {{message}} in {{session}}", "n": 1}
        filled = target.fill(body, "hi {{session}}", "abc", [{"role": "user", "content": "hi"}])
        self.assertEqual(filled["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(filled["note"], "last: hi {{session}} in abc", "a slot inside the message itself is left as written")
        self.assertEqual(filled["n"], 1)

    def test_finding_the_reply(self):
        data = {"choices": [{"message": {"content": "hello"}}]}
        self.assertEqual(target.extract(data, "choices.0.message.content"), "hello")
        for path in ("choices.1.message", "choices.x", "nothing.here"):
            with self.assertRaises(Failure):
                target.extract(data, path)


class Sending(unittest.TestCase):
    def setUp(self):
        self.s = Servers()
        self.addCleanup(self.s.close)

    def sender(self, t, env=None):
        return Sender(t, env=env or {}, sleep=no_sleep, retry_wait=0)

    def test_the_whole_conversation_is_sent_and_the_systems_own_replies_are_its_side_of_it(self):
        url, seen = self.s.scripted(lambda path, body, headers: (200, {}, json.dumps({"reply": f"reply {len(body['messages'])}"})))
        reply, earlier = self.sender(self.s.target(url)).converse(["one", "two"], "three")
        self.assertEqual((reply, earlier), ("reply 5", ["reply 1", "reply 3"]))
        self.assertEqual(seen[-1]["body"]["messages"], [{"role": "user", "content": "one"}, {"role": "assistant", "content": "reply 1"},
                                                         {"role": "user", "content": "two"}, {"role": "assistant", "content": "reply 3"},
                                                         {"role": "user", "content": "three"}])

    def test_a_session_is_opened_for_each_conversation(self):
        url = self.s.practice("weak")
        sender = self.sender(self.s.session_target(url))
        reply, _ = sender.converse(["Could you add a little nautical flavour?"], "What is my leave?")
        self.assertTrue(reply.startswith("Arr"), "the bot remembered the earlier message, so the session held")
        reply, _ = sender.converse([], "What is my leave?")
        self.assertFalse(reply.startswith("Arr"), "a new conversation starts clean")
        self.assertEqual(sender.requests, 5)

    def test_the_key_comes_from_the_environment_and_a_missing_one_is_named(self):
        url = self.s.practice("holding", key="s3cret-for-the-test")
        t = self.s.target(url, request={"url": url + "/chat", "headers": {"Authorization": "Bearer ${ENV:PRACTICE_KEY}"}, "body": {"messages": "{{messages}}"}})
        with self.assertRaises(Problem) as caught:
            self.sender(t)
        self.assertIn("PRACTICE_KEY", str(caught.exception))
        reply, _ = self.sender(t, {"PRACTICE_KEY": "s3cret-for-the-test"}).converse([], "hello")
        self.assertIn("leave", reply)
        with self.assertRaises(Failure) as caught:
            self.sender(t, {"PRACTICE_KEY": "wrong"}).converse([], "hello")
        self.assertIn("status 401", str(caught.exception))

    def test_a_redirect_is_never_followed(self):
        elsewhere, seen_elsewhere = self.s.scripted(lambda *a: (200, {}, json.dumps({"reply": "stolen"})))
        url, _ = self.s.scripted(lambda *a: (307, {"Location": elsewhere + "/chat"}, ""))
        t = self.s.target(url, request={"url": url + "/chat", "headers": {"Authorization": "Bearer ${ENV:K}"}, "body": {"messages": "{{messages}}"}})
        with self.assertRaises(Failure) as caught:
            self.sender(t, {"K": "the-key"}).converse([], "hello")
        self.assertIn("redirect", str(caught.exception))
        self.assertEqual(seen_elsewhere, [], "the key went nowhere else")

    def test_answers_that_are_not_what_was_expected(self):
        cases = {"the answer was not JSON": "<html>login</html>", "nothing at 'reply'": json.dumps({"other": 1}),
                 "was not text": json.dumps({"reply": {"a": 1}}), "larger than 1 MB": json.dumps({"reply": "x" * 1_100_000})}
        for sentence, text in cases.items():
            url, _ = self.s.scripted(lambda *a, text=text: (200, {}, text))
            with self.assertRaises(Failure) as caught:
                self.sender(self.s.target(url)).converse([], "hello")
            self.assertIn(sentence, str(caught.exception))

    def test_a_long_reply_is_cut_and_an_empty_path_takes_the_whole_answer(self):
        url, _ = self.s.scripted(lambda *a: (200, {}, json.dumps({"reply": "y" * 50_000})))
        self.assertEqual(len(self.sender(self.s.target(url)).converse([], "hello")[0]), target.MAX_REPLY)
        url, _ = self.s.scripted(lambda *a: (200, {}, "plain words"))
        self.assertEqual(self.sender(self.s.target(url, reply="")).converse([], "hello")[0], "plain words")

    def test_busy_is_tried_once_more_and_then_given_up(self):
        answers = [(429, {}, ""), (200, {}, json.dumps({"reply": "ok now"}))]
        url, seen = self.s.scripted(lambda *a: answers.pop(0))
        self.assertEqual(self.sender(self.s.target(url)).converse([], "hello")[0], "ok now")
        self.assertEqual(len(seen), 2)
        url, seen = self.s.scripted(lambda *a: (503, {}, ""))
        with self.assertRaises(Failure):
            self.sender(self.s.target(url)).converse([], "hello")
        self.assertEqual(len(seen), 2)

    def test_a_conversation_id_from_the_system_is_checked_before_it_is_used(self):
        url, seen = self.s.scripted(lambda path, body, headers: (200, {}, json.dumps({"id": "../../admin?x=1", "reply": "hi"})))
        with self.assertRaises(Failure) as caught:
            self.sender(self.s.session_target(url)).converse([], "hello")
        self.assertIn("conversation id", str(caught.exception))
        self.assertEqual([r["path"] for r in seen], ["/session"])

    def test_nothing_listening_is_a_plain_failure(self):
        t = self.s.target("http://127.0.0.1:9")
        with self.assertRaises(Failure) as caught:
            self.sender(t).converse([], "hello")
        self.assertIn("could not reach 127.0.0.1", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
