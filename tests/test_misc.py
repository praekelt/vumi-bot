from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase

from vumibot.misc import MiscWorker


class MiscWorkerTestCase(ApplicationTestCase):

    application_class = MiscWorker
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        super(MiscWorkerTestCase, self).setUp()

        self.app = yield self.get_application({
            'worker_name': 'test_misc',
            })

    @inlineCallbacks
    def test_ping(self):
        msg = self.mkmsg_in(content='!ping', from_addr='marco')
        yield self.dispatch(msg)
        self.assertEqual(
            [r"pong."],
            [m['content'] for m in self.get_dispatched_messages()])
