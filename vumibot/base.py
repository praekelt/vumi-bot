# -*- test-case-name: tests.test_base -*-

import re

import redis
from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportUserMessage, TransportEvent
from vumi.application import ApplicationWorker


class CommandFormatException(Exception):
    pass


class BotCommand(object):

    @property
    def command(self):
        raise NotImplementedError("Subclasses should set this.")

    @property
    def pattern(self):
        raise NotImplementedError("Subclasses should set this.")

    def __init__(self, worker, config):
        self.config = config
        self.worker = worker

    def start_command(self):
        pass

    def stop_command(self):
        pass

    def get_compiled_pattern(self):
        if not hasattr(self, '_pattern'):
            self._pattern = re.compile(self.pattern, re.VERBOSE)
        return self._pattern

    def get_help(self):
        return "I grok %s" % (self.pattern,)

    def accepts(self, command):
        return command == self.command

    def handle_command(self, user_id, command_text):
        raise NotImplementedError('Subclasses must implement handle_command()')

    def parse(self, user_id, full_text):
        try:
            command, command_text = full_text.split(' ', 1)
        except ValueError:
            command = full_text
            command_text = ''

        if self.accepts(command):
            return self.handle_command(user_id, command_text)


class BotWorker(ApplicationWorker):

    COMMAND_PREFIX = '!'
    COMMANDS = ()
    FEATURE_NAME = None

    def validate_config(self):
        self.r_config = self.config.get('redis_config', {})
        self.bot_commands = self.config.get('command_configs', {})

    def setup_application(self):
        self.r_server = redis.Redis(**self.r_config)
        self.commands = [cls(self, self.bot_commands.get(self.FEATURE_NAME))
                         for cls in self.COMMANDS]

        for command in self.commands:
            command.setup_command()

    @inlineCallbacks
    def teardown_application(self):
        for command in self.commands:
            yield command.teardown_command()

    def get_commands(self, cls):
        return [command for command in self.commands
                    if isinstance(command, cls)]

    @inlineCallbacks
    def consume_user_message(self, message):
        content = message['content']
        if content.startswith(self.COMMAND_PREFIX):
            prefix, cmd = content.split(self.COMMAND_PREFIX, 1)
            for command_handler in self.commands:
                try:
                    reply = yield command_handler.parse(message.user(), cmd)
                    if reply:
                        self.reply_to(message, '%s: %s' % (
                            message['from_addr'], reply))
                except CommandFormatException, e:
                    self.reply_to(message, "%s: that does not compute. %s" % (
                        message['from_addr'], command_handler.get_help()))
                except Exception, e:
                    self.reply_to(message, '%s: eep! %s.' % (
                        message['from_addr'], e))

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
