# -*- test-case-name: tests.test_coffee -*-

"""Track coffee on IRC."""

import json

from twisted.internet.defer import inlineCallbacks, returnValue
from vumi import log
from vumi.config import ConfigDict
from vumi.persist.txredis_manager import TxRedisManager

from vumibot.base import BotMessageProcessor, botcommand


class CoffeeMessageProcessorConfig(BotMessageProcessor.CONFIG_CLASS):
    redis_manager = ConfigDict(
        "Redis manager config.", static=True, default={})


class CoffeeMessageProcessor(BotMessageProcessor):
    """Track coffee on IRC

    Configuration
    -------------
    worker_name : str
        Name of this worker. Used as part of the Redis key prefix.
    """

    CONFIG_CLASS = CoffeeMessageProcessorConfig

    @inlineCallbacks
    def setup_message_processor(self):
        self.base_redis = yield TxRedisManager.from_config(
            self.config.redis_manager)
        self.redis = self.base_redis.sub_manager('ircbot:coffee')

    @inlineCallbacks
    def teardown_message_processor(self):
        yield self.redis.close_manager()
        yield self.base_redis.close_manager()

    def rkey_violation(self, channel, recipient):
        return "%s:%s" % (channel, recipient)

    def store_violation(self, channel, recipient, sender, text):
        violation_key = self.rkey_violation(channel, recipient)
        value = json.dumps([sender, text])
        return self.redis.rpush(violation_key, value)

    @inlineCallbacks
    def retrieve_violations(self, channel, recipient, delete=False):
        violation_key = self.rkey_violation(channel, recipient)
        violations = yield self.redis.lrange(violation_key, 0, -1)
        if delete:
            yield self.redis.delete(violation_key)
        returnValue([json.loads(value) for value in violations])

    @botcommand(r'$')
    @inlineCallbacks
    def cmd_mycoffee(self, message, params):
        "Usage: !mycoffee"

        channel = message['group']
        nickname = message.user()

        violations = yield self.retrieve_violations(
            channel, nickname, delete=True)
        if violations:
            log.msg("Time to deliver some violations:", violations)
        returnValue([
            "%s, %s says you butchered this: %s" % (
                nickname, violation_sender, violation_text)
            for violation_sender, violation_text in violations])

    @botcommand(r'(?P<target>\S+)\s+(?P<violation_text>.+)$')
    @inlineCallbacks
    def cmd_coffee(self, message, params, target, violation_text):
        "Usage: !coffee <nick> <violation>"

        channel = message['group']

        recipient = target.lower()
        sender = message['from_addr']
        yield self.store_violation(channel, recipient, sender, violation_text)
        returnValue("Oh boy!")
