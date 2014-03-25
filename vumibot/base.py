# -*- test-case-name: tests.test_base -*-

import re

from twisted.internet.defer import inlineCallbacks
from twisted.python import log

from vumi.application import ApplicationWorker
from vumi.config import Config, ConfigDict, ConfigText
from vumi.utils import load_class_by_string


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

    def parse_command(self, command_text):
        match = self.get_compiled_pattern().match(command_text)
        if not match:
            raise CommandFormatException()
        return match


class BotMessageProcessor(object):
    CONFIG_CLASS = Config

    def __init__(self, app_worker, config):
        self._app_worker = app_worker
        self.config = self.CONFIG_CLASS(config)

    def setup_message_processor(self):
        pass

    def teardown_message_processor(self):
        pass

    def handle_message(self, message):
        pass

    def handle_command(self, message, content):
        command, params = (content.split(None, 1) + ['', ''])[:2]
        handler = self.find_command(command)
        if not handler:
            return

        match = handler.pattern.match(params.strip())
        if not match:
            return "that does not compute. %s" % (handler.__doc__,)
        return handler(
            message, match.groups(), **match.groupdict())

    def find_command(self, command_name):
        handler = getattr(self, 'cmd_%s' % (command_name,), None)
        if hasattr(handler, 'pattern') and callable(handler):
            return handler

    def reply_to(self, original_message, content, *args, **kw):
        return self._app_worker.reply_to(
            original_message, content, *args, **kw)

    def reply_to_group(self, original_message, content, *args, **kw):
        return self._app_worker.reply_to_group(
            original_message, content, *args, **kw)


class BotWorkerConfig(ApplicationWorker.CONFIG_CLASS):
    command_prefix = ConfigText(
        "Prefix for bot commands.", default="!", static=True)
    message_processors = ConfigDict(
        "Mapping from class name to config dict.", static=True)


class BotWorker(ApplicationWorker):
    CONFIG_CLASS = BotWorkerConfig

    @inlineCallbacks
    def setup_application(self):
        config = self.get_static_config()
        self.command_prefix = config.command_prefix
        self.message_processors = []
        for proc_cls, proc_config in config.message_processors.iteritems():
            cls = load_class_by_string(proc_cls)
            proc = cls(self, proc_config)
            self.message_processors.append(proc)
            yield proc.setup_message_processor()

    @inlineCallbacks
    def teardown_application(self):
        while self.message_processors:
            yield self.message_processors.pop().teardown_message_processor()

    def parse_user_message(self, message):
        content = message['content']
        is_command = False

        if content.startswith(self.command_prefix):
            is_command = True
            content = content[len(self.command_prefix):]
        elif message['to_addr'] is not None:
            is_command = True

        return (is_command, content)

    def listify_replies(self, replies):
        if not replies:
            return []
        if isinstance(replies, basestring):
            return [replies]
        return replies

    @inlineCallbacks
    def consume_user_message(self, message):
        replies = []

        for proc in self.message_processors:
            try:
                rpl = yield proc.handle_message(message)
                replies.extend(self.listify_replies(rpl))
            except Exception:
                log.err()

            try:
                is_command, content = self.parse_user_message(message)
                if is_command:
                    rpl = yield proc.handle_command(message, content)
                    replies.extend(self.listify_replies(rpl))
            except Exception, e:
                log.err()
                replies.append('eep! %s: %s.' % (type(e).__name__, e))

        for reply in replies:
            self.reply_to(message, reply)
