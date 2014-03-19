# -*- test-case-name: tests.test_mexican -*-
# -*- coding: utf-8 -*-

"""
Mexican commands.
"""

import random

from twisted.internet.defer import inlineCallbacks

from vumibot.base import BotMessageProcessor, botcommand


class MexicanMessageProcessor(BotMessageProcessor):
    @botcommand(r'(?P<subcommand>\w*)!?')
    def cmd_mexican(self, message, params, subcommand):
        handler = getattr(self, 'mexican_%s' % subcommand, None)
        if not handler:
            return u"¿Qué?"
        return handler(message)

    def mexican_wave(self, message):
        return [
            "\o/\o/.o..o..o..o.",
            ".o.\o/\o/.o..o..o.",
            ".o..o.\o/\o/.o..o.",
            ".o..o..o.\o/\o/.o.",
            ".o..o..o..o.\o/\o/",
            ]

    @inlineCallbacks
    def mexican_standoff(self, message):
        message['helper_metadata']['irc'] = {'irc_command': 'ACTION'}
        yield self.reply_to(
            message, "points a pistol at %s." % message.user())

    def mexican_food(self, message):
        food = random.choice([
                "Nachos",
                "Tacos",
                "Quesadillas",
                "Burritos",
                "Tamales",
                ])
        return u"¡%s!" % food
