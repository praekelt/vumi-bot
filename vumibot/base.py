import re

import redis
from twisted.internet.defer import inlineCallbacks

from vumi.application import ApplicationWorker


class CommandFormatException(Exception):
    pass


class BotCommand(object):

    def start_command(self):
        pass

    def stop_command(self):
        pass

    def get_command(self):
        raise NotImplementedError("Subclasses should implement this.")

    def get_pattern(self):
        raise NotImplementedError("Subclasses should implement this.")

    def get_compiled_pattern(self):
        if not hasattr(self, '_pattern'):
            self._pattern = re.compile(self.get_pattern(), re.VERBOSE)
        return self._pattern

    def get_help(self):
        return "I grok %s" % (self.get_pattern(),)

    def accepts(self, command):
        return command == self.get_command()

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
        self.commands = [
            cmd_cls(self.r_server, self.bot_commands.get(self.FEATURE_NAME))
            for cmd_cls in self.COMMANDS]

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
