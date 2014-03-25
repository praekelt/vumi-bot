import re

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.helpers import ApplicationHelper
from vumi.config import ConfigText
from vumi.tests.helpers import VumiTestCase

from vumibot.base import BotWorker, BotMessageProcessor, botcommand


class ToyMessageProcessorConfig(BotMessageProcessor.CONFIG_CLASS):
    reply = ConfigText("Reply text.", static=True)


class ToyMessageProcessor1(BotMessageProcessor):
    CONFIG_CLASS = ToyMessageProcessorConfig

    @botcommand
    def cmd_toy(self, message, params):
        return self.config.reply

    @botcommand
    def cmd_toy1(self, message, params):
        return self.config.reply

    def cmd_callable(self, message, params):
        "This is callable, but has not `pattern` attribute."


class ToyMessageProcessor2(BotMessageProcessor):
    CONFIG_CLASS = ToyMessageProcessorConfig

    @botcommand(r'')
    def cmd_toy(self, message, params):
        return self.config.reply

    @botcommand(r'')
    def cmd_toy2(self, message, params):
        return self.config.reply

    cmd_re = re.compile(
        "This has a `pattern` attribute, but is not callable.")


def cls_string(cls):
    return '.'.join((cls.__module__, cls.__name__))


class TestBotWorker(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(ApplicationHelper(BotWorker))
        self.app = yield self.app_helper.get_application({
            'message_processors': {
                cls_string(ToyMessageProcessor1): {'reply': 'foo'},
                cls_string(ToyMessageProcessor2): {'reply': 'bar'},
            }})

    def get_replies_content(self):
        return [m['content']
                for m in self.app_helper.get_dispatched_outbound()]

    def make_dispatch_inbound(self, content, group="#channel", to_addr=None):
        return self.app_helper.make_dispatch_inbound(
            content, from_addr="nick", group=group, to_addr=to_addr)

    @inlineCallbacks
    def test_both(self):
        yield self.make_dispatch_inbound('!toy')
        self.assertEqual(['foo', 'bar'], self.get_replies_content())

    @inlineCallbacks
    def test_each(self):
        yield self.make_dispatch_inbound('!toy1')
        self.assertEqual(['foo'], self.get_replies_content())

        self.app_helper.clear_all_dispatched()
        yield self.make_dispatch_inbound('!toy2')
        self.assertEqual(['bar'], self.get_replies_content())

    @inlineCallbacks
    def test_non_commands(self):
        yield self.make_dispatch_inbound('!callable')
        yield self.make_dispatch_inbound('!re')
        self.assertEqual([], self.get_replies_content())

    @inlineCallbacks
    def test_prefix_only(self):
        yield self.make_dispatch_inbound('!')
        self.assertEqual([], self.get_replies_content())

    @inlineCallbacks
    def test_directed_commands(self):
        # Group-directed.
        yield self.make_dispatch_inbound('toy1', to_addr='bot')
        self.assertEqual(['foo'], self.get_replies_content())

        # One-to-one.
        self.app_helper.clear_all_dispatched()
        yield self.make_dispatch_inbound('toy1', to_addr='bot', group=None)
        self.assertEqual(['foo'], self.get_replies_content())
