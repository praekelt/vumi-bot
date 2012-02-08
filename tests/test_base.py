from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vumibot.base import BotCommand, BotWorker


class ToyBotCommand(BotCommand):

    pattern = r''

    def setup_command(self):
        self.reply = self.config['reply']

    def teardown_command(self):
        pass

    def get_help(self):
        return "Test the things."

    def handle_command(self, user_id, command_text):
        return self.reply


class ToyBotCommand1(ToyBotCommand):
    command = "toy1"


class ToyBotCommand2(ToyBotCommand):
    command = "toy2"


class ToyBotCommandBoth(ToyBotCommand):
    command = "toy"


class ToyBotWorker1(BotWorker):
    COMMANDS = (ToyBotCommandBoth, ToyBotCommand1)
    FEATURE_NAME = "toy1"


class ToyBotWorker2(BotWorker):
    COMMANDS = (ToyBotCommandBoth, ToyBotCommand2)
    FEATURE_NAME = "toy2"


class BotWorkerTestCase(ApplicationTestCase):

    timeout = 1

    @inlineCallbacks
    def setUp(self):
        yield super(BotWorkerTestCase, self).setUp()

        self.fake_redis = FakeRedis()

        self.app1 = yield self.get_application({
                'worker_name': 'test_app1',
                'command_configs': {
                    'toy1': {
                        'reply': 'foo',
                        },
                    },
                }, ToyBotWorker1)
        self.app1.r_server = self.fake_redis

        self.app2 = yield self.get_application({
                'worker_name': 'test_app2',
                'command_configs': {
                    'toy2': {
                        'reply': 'bar',
                        },
                    },
                }, ToyBotWorker2)
        self.app1.r_server = self.fake_redis

    @inlineCallbacks
    def tearDown(self):
        yield super(BotWorkerTestCase, self).tearDown()
        self.fake_redis.teardown()

    @inlineCallbacks
    def test_both(self):
        msg = self.mkmsg_in(content='!toy')
        yield self.dispatch(msg)
        self.assertEqual(2, len(self.get_dispatched_messages()))

        # This should probably be in its own test.
        # We use a different queue name so that we can have multiple workers
        # listening to the same routing key.
        self.assertTrue("sphex.inbound.toy1" in self._amqp.queues)
        self.assertTrue("sphex.inbound.toy2" in self._amqp.queues)
        self.assertTrue("sphex.inbound" not in self._amqp.queues)

    @inlineCallbacks
    def test_each(self):
        msg = self.mkmsg_in(content='!toy1')
        yield self.dispatch(msg)
        self.assertEqual(1, len(self.get_dispatched_messages()))

        msg = self.mkmsg_in(content='!toy2')
        yield self.dispatch(msg)
        self.assertEqual(2, len(self.get_dispatched_messages()))
