"""Tests for vumibot.memo."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.message import TransportUserMessage
from vumi.tests.helpers import VumiTestCase

from tests.helpers import BotMessageProcessorHelper
from vumibot.memo import MemoMessageProcessor


class TestMemoWorker(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.proc_helper = self.add_helper(
            BotMessageProcessorHelper(MemoMessageProcessor))
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
    def test_no_memos(self):
        yield self.send("Message from someone with no messages.")
        replies = yield self.recv()
        self.assertEquals([], replies)

    @inlineCallbacks
    def test_leave_memo(self):
        yield self.send('!tell memoed hey there', channel='#test')
        memos = yield self.proc.retrieve_memos('#test', 'memoed')
        self.assertEquals(memos, [['testnick', 'hey there']])
        replies = yield self.recv()
        self.assertEqual(replies, [
            ('reply', 'Sure thing, boss.'),
            ])

    @inlineCallbacks
    def test_leave_memo_nick_canonicalization(self):
        yield self.send('!tell MeMoEd hey there', channel='#test')
        memos = yield self.proc.retrieve_memos('#test', 'memoed')
        self.assertEquals(memos, [['testnick', 'hey there']])

    @inlineCallbacks
    def test_ask_alias(self):
        yield self.send('!ask wisdomfont how do i? ', channel='#test')
        memos = yield self.proc.retrieve_memos('#test', 'wisdomfont')
        self.assertEquals(memos, [['testnick', 'how do i?']])

    @inlineCallbacks
    def test_send_memos(self):
        yield self.send('!tell testmemo this is memo 1', channel='#test')
        yield self.send('!tell testmemo this is memo 2', channel='#test')
        yield self.send('!tell testmemo this is a different channel',
                        channel='#another')

        # replies to setting memos
        replies = yield self.recv(3)
        self.proc_helper.clear_all_dispatched()

        yield self.send('ping', channel='#test', from_addr='testmemo')
        replies = yield self.recv(2)
        self.assertEqual(replies, [
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is memo 1'),
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is memo 2'),
            ])
        self.proc_helper.clear_all_dispatched()

        yield self.send('ping', channel='#another', from_addr='testmemo')
        replies = yield self.recv(1)
        self.assertEqual(replies, [
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is a different channel'),
            ])
