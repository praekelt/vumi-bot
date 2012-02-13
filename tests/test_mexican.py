
from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase

from vumibot.mexican import MexicanWorker


class MexicanWorkerTestCase(ApplicationTestCase):

    application_class = MexicanWorker
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        super(MexicanWorkerTestCase, self).setUp()

        self.app = yield self.get_application({
            'worker_name': 'test_mexican',
            })

    @inlineCallbacks
    def test_wave(self):
        msg = self.mkmsg_in(content='!mexican wave', from_addr='jose')
        yield self.dispatch(msg)
        self.assertEqual([
                r"jose: \o/\o/.o..o..o..o.",
                r"jose: .o.\o/\o/.o..o..o.",
                r"jose: .o..o.\o/\o/.o..o.",
                r"jose: .o..o..o.\o/\o/.o.",
                r"jose: .o..o..o..o.\o/\o/",
                ], [m['content'] for m in self.get_dispatched_messages()])

    @inlineCallbacks
    def test_standoff(self):
        msg = self.mkmsg_in(content='!mexican standoff', from_addr='jose')
        yield self.dispatch(msg)
        [msg] = self.get_dispatched_messages()
        self.assertEqual("points a pistol at jose.", msg['content'])
        self.assertEqual(
            "ACTION", msg['helper_metadata']['irc']['irc_command'])
