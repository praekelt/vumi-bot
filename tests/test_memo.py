"""Tests for vumibot.memo."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vumibot.memo import MemoWorker
from vumi.message import TransportUserMessage


class TestMemoWorker(ApplicationTestCase):

    application_class = MemoWorker

    @inlineCallbacks
    def setUp(self):
        super(TestMemoWorker, self).setUp()
        self.worker = yield self.get_application({
            'worker_name': 'testmemo',
            })
        self.worker.r_server = FakeRedis()

    def tearDown(self):
        self.worker.r_server.teardown()

    @inlineCallbacks
    def send(self, content, from_addr='testnick', channel=None):
        transport_metadata = {}
        helper_metadata = {}
        if channel is not None:
            transport_metadata['irc_channel'] = channel
            helper_metadata['irc'] = {'irc_channel': channel}

        msg = self.mkmsg_in(content=content, from_addr=from_addr,
                            group=channel, helper_metadata=helper_metadata,
                            transport_metadata=transport_metadata)
        yield self.dispatch(msg)

    def clear_messages(self):
        self._amqp.clear_messages('vumi', '%s.outbound' % self.transport_name)

    @inlineCallbacks
    def recv(self, n=0):
        msgs = yield self.wait_for_dispatched_messages(n)

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
        self.assertEquals(self.worker.retrieve_memos('#test', 'memoed'),
                          [['testnick', 'hey there']])
        replies = yield self.recv()
        self.assertEqual(replies, [
            ('reply', 'testnick: Sure thing, boss.'),
            ])

    @inlineCallbacks
    def test_leave_memo_nick_canonicalization(self):
        yield self.send('!tell MeMoEd hey there', channel='#test')
        self.assertEquals(self.worker.retrieve_memos('#test', 'memoed'),
                          [['testnick', 'hey there']])

    @inlineCallbacks
    def test_send_memos(self):
        yield self.send('!tell testmemo this is memo 1', channel='#test')
        yield self.send('!tell testmemo this is memo 2', channel='#test')
        yield self.send('!tell testmemo this is a different channel',
                        channel='#another')

        # replies to setting memos
        replies = yield self.recv(3)
        self.clear_messages()

        yield self.send('ping', channel='#test', from_addr='testmemo')
        replies = yield self.recv(2)
        self.assertEqual(replies, [
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is memo 1'),
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is memo 2'),
            ])
        self.clear_messages()

        yield self.send('ping', channel='#another', from_addr='testmemo')
        replies = yield self.recv(1)
        self.assertEqual(replies, [
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is a different channel'),
            ])
