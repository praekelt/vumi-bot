# -*- test-case-name: tests.test_memo -*-

"""Demo workers for constructing a simple IRC bot."""

import json

import redis
from twisted.python import log

from twisted.internet.defer import inlineCallbacks, returnValue

from vumibot.base import BotWorker, botcommand


class MemoWorker(BotWorker):
    """Watches for memos to users and notifies users of memos when users
    appear.

    Configuration
    -------------
    worker_name : str
        Name of this worker. Used as part of the Redis key prefix.
    """

    def validate_config(self):
        self.redis_config = self.config.get('redis', {})
        self.r_prefix = "ircbot:memos:%s" % (self.config['worker_name'],)

    def setup_bot(self):
        self.r_server = redis.Redis(**self.redis_config)

    def rkey_memo(self, channel, recipient):
        return "%s:%s:%s" % (self.r_prefix, channel, recipient)

    def store_memo(self, channel, recipient, sender, text):
        memo_key = self.rkey_memo(channel, recipient)
        value = json.dumps([sender, text])
        self.r_server.rpush(memo_key, value)

    def retrieve_memos(self, channel, recipient, delete=False):
        memo_key = self.rkey_memo(channel, recipient)
        memos = self.r_server.lrange(memo_key, 0, -1)
        if delete:
            self.r_server.delete(memo_key)
        return [json.loads(value) for value in memos]

    @inlineCallbacks
    def handle_message(self, message):
        nickname = message.user()
        irc_metadata = message['helper_metadata'].get('irc', {})
        channel = irc_metadata.get('irc_channel', 'unknown')

        memos = self.retrieve_memos(channel, nickname, delete=True)
        if memos:
            log.msg("Time to deliver some memos:", memos)
        for memo_sender, memo_text in memos:
            yield self.reply_to(message, "%s, %s asked me tell you: %s" % (
                    nickname, memo_sender, memo_text))

        if irc_metadata.get('addressed_to_transport', True):
            rpl = yield self.handle_command(
                message, message['content'].split(None, 1)[-1])
            returnValue(rpl)

    @botcommand(r'(?P<target>\S+)\s+(?P<memo_text>.+)$')
    def cmd_tell(self, message, params, target, memo_text):
        "Usage: !tell <nick> <message>"

        irc_metadata = message['helper_metadata'].get('irc', {})
        channel = irc_metadata.get('irc_channel', 'unknown')

        recipient = target.lower()
        sender = message['from_addr']
        self.store_memo(channel, recipient, sender, memo_text)
        return "Sure thing, boss."
