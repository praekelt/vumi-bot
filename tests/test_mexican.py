
from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from tests.helpers import BotMessageProcessorHelper
from vumibot.mexican import MexicanMessageProcessor


class TestMexicanMessageProcessor(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.proc_helper = self.add_helper(
            BotMessageProcessorHelper(MexicanMessageProcessor))
        self.proc = yield self.proc_helper.get_message_processor({})

    @inlineCallbacks
    def test_wave(self):
        yield self.proc_helper.make_dispatch_inbound(
            '!mexican wave', from_addr='jose')
        self.assertEqual([
            r"\o/\o/.o..o..o..o.",
            r".o.\o/\o/.o..o..o.",
            r".o..o.\o/\o/.o..o.",
            r".o..o..o.\o/\o/.o.",
            r".o..o..o..o.\o/\o/",
        ], [m['content'] for m in self.proc_helper.get_dispatched_outbound()])

    @inlineCallbacks
    def test_standoff(self):
        yield self.proc_helper.make_dispatch_inbound(
            '!mexican standoff', from_addr='jose')
        [msg] = self.proc_helper.get_dispatched_outbound()
        self.assertEqual("points a pistol at jose.", msg['content'])
        self.assertEqual(
            "ACTION", msg['helper_metadata']['irc']['irc_command'])

    @inlineCallbacks
    def test_food(self):
        for _ in range(50):
            yield self.proc_helper.make_dispatch_inbound(
                '!mexican food', from_addr='jose')
        msgs = [m['content']
                for m in self.proc_helper.get_dispatched_outbound()]
        self.assertTrue(1 < len(set(msgs)) <= 5)
