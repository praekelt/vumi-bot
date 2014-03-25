from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from tests.helpers import BotMessageProcessorHelper
from vumibot.misc import MiscMessageProcessor


class TestMiscMessageProcessor(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.proc_helper = self.add_helper(
            BotMessageProcessorHelper(MiscMessageProcessor))
        self.proc = yield self.proc_helper.get_message_processor({})

    @inlineCallbacks
    def test_ping(self):
        yield self.proc_helper.make_dispatch_inbound(
            '!ping', from_addr='marco')
        self.assertEqual(
            [r"pong."],
            [m['content'] for m in self.proc_helper.get_dispatched_outbound()])
