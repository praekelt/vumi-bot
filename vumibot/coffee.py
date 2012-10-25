# -*- test-case-name: tests.test_coffee -*-

"""Track coffee on IRC."""

import json

import redis
from twisted.python import log
from vumibot.base import BotWorker, botcommand


class CoffeeWorker(BotWorker):
    """Track coffee on IRC

    Configuration
    -------------
    worker_name : str
        Name of this worker. Used as part of the Redis key prefix.
    """

    def validate_config(self):
        self.redis_config = self.config.get('redis', {})
        self.r_prefix = "ircbot:coffee:%s" % (self.config['worker_name'],)

    def setup_bot(self):
        self.r_server = redis.Redis(**self.redis_config)

    def rkey_violation(self, channel, recipient):
        return "%s:%s:%s" % (self.r_prefix, channel, recipient)

    def store_violation(self, channel, recipient, sender, text):
        violation_key = self.rkey_violation(channel, recipient)
        value = json.dumps([sender, text])
        self.r_server.rpush(violation_key, value)

    def retrieve_violations(self, channel, recipient, delete=False):
        violation_key = self.rkey_violation(channel, recipient)
        violations = self.r_server.lrange(violation_key, 0, -1)
        if delete:
            self.r_server.delete(violation_key)
        return [json.loads(value) for value in violations]

    @botcommand(r'$')
    def cmd_mycoffee(self, message, params):
        "Usage: !mycoffee"

        channel = message['group']
        nickname = message.user()

        violations = self.retrieve_violations(channel, nickname, delete=True)
        if violations:
            log.msg("Time to deliver some violations:", violations)
        return ["%s, %s says you butchered the language with: %s" % (
                    nickname, violation_sender, violation_text)
                    for violation_sender, violation_text in violations]

    @botcommand(r'(?P<target>\S+)\s+(?P<violation_text>.+)$')
    def cmd_coffee(self, message, params, target, violation_text):
        "Usage: !coffee <nick> <violation>"

        channel = message['group']

        recipient = target.lower()
        sender = message['from_addr']
        self.store_violation(channel, recipient, sender, violation_text)
        return "Oh boy!"
