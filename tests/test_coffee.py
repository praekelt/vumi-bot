"""Tests for vumibot.coffee"""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.tests.helpers import VumiTestCase

from tests.helpers import BotMessageProcessorHelper
from vumibot.coffee import CoffeeMessageProcessor


class TestCoffeeWorker(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.proc_helper = self.add_helper(
            BotMessageProcessorHelper(CoffeeMessageProcessor))
        self.proc = yield self.proc_helper.get_message_processor({})

    def send(self, content, from_addr='testnick', channel=None):
        transport_metadata = {}
        helper_metadata = {}
        if channel is not None:
            transport_metadata['irc_channel'] = channel
            helper_metadata['irc'] = {'irc_channel': channel}

        return self.proc_helper.make_dispatch_inbound(
            content, from_addr=from_addr, group=channel,
            helper_metadata=helper_metadata,
            transport_metadata=transport_metadata)

    @inlineCallbacks
    def recv(self, n=0):
        msgs = yield self.proc_helper.wait_for_dispatched_outbound(n)

        def reply_code(msg):
            if msg['session_event'] == TransportUserMessage.SESSION_CLOSE:
                return 'end'
            return 'reply'

        returnValue([(reply_code(msg), msg['content']) for msg in msgs])

    @inlineCallbacks
    def test_no_violations(self):
        yield self.send("Message from someone with no messages.")
        replies = yield self.recv()
        self.assertEquals([], replies)

    @inlineCallbacks
    def test_leave_violation(self):
        yield self.send('!coffee memoed mistake', channel='#test')
        violations = yield self.proc.retrieve_violations('#test', 'memoed')
        self.assertEquals(violations, [['testnick', 'mistake']])
        replies = yield self.recv()
        self.assertEqual(replies, [
            ('reply', 'Oh boy!'),
            ])

    @inlineCallbacks
    def test_leave_violation_nick_canonicalization(self):
        yield self.send('!coffee MeMoEd boooo', channel='#test')
        violations = yield self.proc.retrieve_violations('#test', 'memoed')
        self.assertEquals(violations, [['testnick', 'boooo']])

    @inlineCallbacks
    def test_send_violations(self):
        yield self.send('!coffee testmemo this is violation1', channel='#test')
        yield self.send('!coffee testmemo this is violation2', channel='#test')
        yield self.send('!coffee testmemo this is a different channel',
                        channel='#another')

        # replies to setting memos
        replies = yield self.recv(3)
        self.proc_helper.clear_all_dispatched()

        yield self.send('!mycoffee', channel='#test', from_addr='testmemo')
        replies = yield self.recv(2)

        self.assertEqual(replies, [
            ('reply', 'testmemo, testnick says you butchered this:'
             ' this is violation1'),
            ('reply', 'testmemo, testnick says you butchered this:'
             ' this is violation2'),
            ])
