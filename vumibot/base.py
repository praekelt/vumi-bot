# -*- test-case-name: tests.test_base -*-

import re

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportUserMessage, TransportEvent
from vumi.application import ApplicationWorker


class CommandFormatException(Exception):
    pass


def botcommand(func_or_pattern):
    if callable(func_or_pattern):
        return botcommand(r'')(func_or_pattern)
    pattern = re.compile(func_or_pattern)

    def patternator(func):
        func.pattern = pattern
        return func

    return patternator


class BotWorker(ApplicationWorker):

    DEFAULT_COMMAND_PREFIX = '!'
    FEATURE_NAME = None

    def setup_application(self):
        self.command_prefix = self.config.get(
            'command_prefix', self.DEFAULT_COMMAND_PREFIX)
        return self.setup_bot()

    def teardown_application(self):
        return self.teardown_bot()

    def setup_bot(self):
        pass

    def teardown_bot(self):
        pass

    def find_command(self, command_name):
        handler = getattr(self, 'cmd_%s' % (command_name,), None)
        if hasattr(handler, 'pattern') and callable(handler):
            return handler

    def listify_replies(self, replies):
        if not replies:
            return []
        if isinstance(replies, basestring):
            return [replies]
        return replies

    @inlineCallbacks
    def consume_user_message(self, message):
        try:
            rpl = yield self.handle_message(message)
            replies = self.listify_replies(rpl)

            content = message['content']
            if content.startswith(self.command_prefix):
                content = message['content'][len(self.command_prefix):]
                rpl = yield self.handle_command(message, content)
                replies.extend(self.listify_replies(rpl))

            for reply in replies:
                self.reply_to(message, '%s: %s' % (
                        message['from_addr'], reply))
        except Exception, e:
            self.reply_to(message, '%s: eep! %s.' % (
                    message['from_addr'], e))

    def handle_message(self, message):
        pass

    def handle_command(self, message, content):
        command, params = (content.split(None, 1) + [''])[:2]
        handler = self.find_command(command)
        if not handler:
            return

        match = handler.pattern.match(params.strip())
        if not match:
            return "that does not compute. %s" % (handler.__doc__,)
        return handler(
            message, match.groups(), **match.groupdict())

    @inlineCallbacks
    def _setup_transport_consumer(self):
        rkey = '%(transport_name)s.inbound' % self.config
        self.transport_consumer = yield self.consume(
            rkey,
            self.dispatch_user_message,
            queue_name="%s.%s" % (rkey, self.FEATURE_NAME),
            message_class=TransportUserMessage)
        self._consumers.append(self.transport_consumer)

    @inlineCallbacks
    def _setup_event_consumer(self):
        rkey = '%(transport_name)s.event' % self.config
        self.transport_event_consumer = yield self.consume(
            rkey,
            self.dispatch_event,
            queue_name="%s.%s" % (rkey, self.FEATURE_NAME),
            message_class=TransportEvent)
        self._consumers.append(self.transport_event_consumer)
