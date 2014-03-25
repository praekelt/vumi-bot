# -*- test-case-name: tests.test_memo -*-

"""Demo workers for constructing a simple IRC bot."""

import json

from twisted.internet.defer import inlineCallbacks, returnValue
from vumi import log
from vumi.config import ConfigDict
from vumi.persist.txredis_manager import TxRedisManager

from vumibot.base import BotMessageProcessor, botcommand


class MemoMessageProcessorConfig(BotMessageProcessor.CONFIG_CLASS):
    redis_manager = ConfigDict(
        "Redis manager config.", static=True, default={})


class MemoMessageProcessor(BotMessageProcessor):
    """Watches for memos to users and notifies users of memos when users
    appear.

    Configuration
    -------------
    worker_name : str
        Name of this worker. Used as part of the Redis key prefix.
    """

    CONFIG_CLASS = MemoMessageProcessorConfig

    @inlineCallbacks
    def setup_message_processor(self):
        self.base_redis = yield TxRedisManager.from_config(
            self.config.redis_manager)
        self.redis = self.base_redis.sub_manager('ircbot:memo')

    @inlineCallbacks
    def teardown_message_processor(self):
        yield self.redis.close_manager()
        yield self.base_redis.close_manager()

    def rkey_memo(self, channel, recipient):
        return "%s:%s" % (channel, recipient)

    def store_memo(self, channel, recipient, sender, text):
        memo_key = self.rkey_memo(channel, recipient)
        value = json.dumps([sender, text])
        return self.redis.rpush(memo_key, value)

    @inlineCallbacks
    def retrieve_memos(self, channel, recipient, delete=False):
        memo_key = self.rkey_memo(channel, recipient)
        memos = yield self.redis.lrange(memo_key, 0, -1)
        if delete:
            yield self.redis.delete(memo_key)
        returnValue([json.loads(value) for value in memos])

    @inlineCallbacks
    def handle_message(self, message):
        nickname = message.user()
        channel = message['group']

        memos = yield self.retrieve_memos(channel, nickname, delete=True)
        if memos:
            log.msg("Time to deliver some memos:", memos)
        for memo_sender, memo_text in memos:
            yield self.reply_to_group(
                message, "%s, %s asked me tell you: %s" % (
                    nickname, memo_sender, memo_text))

    @botcommand(r'(?P<target>\S+)\s+(?P<memo_text>.+)$')
    @inlineCallbacks
    def cmd_tell(self, message, params, target, memo_text):
        "Usage: !tell <nick> <message>"

        channel = message['group']

        recipient = target.lower()
        sender = message['from_addr']
        yield self.store_memo(channel, recipient, sender, memo_text)
        returnValue("Sure thing, boss.")

    cmd_ask = cmd_tell  # alias for polite questions
