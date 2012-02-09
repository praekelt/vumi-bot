import re

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vumibot.base import BotWorker, botcommand


class ToyBotWorker1(BotWorker):
    FEATURE_NAME = "toy1"

    @botcommand
    def cmd_toy(self, message, params):
        return self.config['reply']

    @botcommand
    def cmd_toy1(self, message, params):
        return self.config['reply']

    def cmd_callable(self, message, params):
        "This is callable, but has not `pattern` attribute."


class ToyBotWorker2(BotWorker):
    FEATURE_NAME = "toy2"

    @botcommand(r'')
    def cmd_toy(self, message, params):
        return self.config['reply']

    @botcommand(r'')
    def cmd_toy2(self, message, params):
        return self.config['reply']

    cmd_re = re.compile(
        "This has a `pattern` attribute, but is not callable.")


class BotWorkerTestCase(ApplicationTestCase):

    timeout = 1

    @inlineCallbacks
    def setUp(self):
        yield super(BotWorkerTestCase, self).setUp()

        self.fake_redis = FakeRedis()

        self.app1 = yield self.get_application({
                'worker_name': 'test_app1',
                'reply': 'foo',
                }, ToyBotWorker1)
        self.app1.r_server = self.fake_redis

        self.app2 = yield self.get_application({
                'worker_name': 'test_app2',
                'reply': 'bar',
                }, ToyBotWorker2)
        self.app1.r_server = self.fake_redis

    @inlineCallbacks
    def tearDown(self):
        yield super(BotWorkerTestCase, self).tearDown()
        self.fake_redis.teardown()

    def get_msgs_content(self):
        return [m['content'] for m in self.get_dispatched_messages()]

    def mkmsg_in(self, content):
        return super(BotWorkerTestCase, self).mkmsg_in(
            content=content, from_addr="nick")

    @inlineCallbacks
    def test_both(self):
        msg = self.mkmsg_in(content='!toy')
        yield self.dispatch(msg)
        self.assertEqual(['nick: foo', 'nick: bar'], self.get_msgs_content())

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
        self.assertEqual(['nick: foo'], self.get_msgs_content())

        msg = self.mkmsg_in(content='!toy2')
        yield self.dispatch(msg)
        self.assertEqual(['nick: foo', 'nick: bar'], self.get_msgs_content())

    @inlineCallbacks
    def test_non_commands(self):
        yield self.dispatch(self.mkmsg_in(content='!callable'))
        yield self.dispatch(self.mkmsg_in(content='!re'))
        yield self.dispatch(self.mkmsg_in(content='!'))
        self.assertEqual([], self.get_msgs_content())
