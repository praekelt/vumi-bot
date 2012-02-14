# -*- test-case-name: tests.test_mexican -*-
# -*- coding: utf-8 -*-

"""
Mexican commands.
"""

import random

from vumibot.base import BotWorker, botcommand


class MexicanWorker(BotWorker):
    FEATURE_NAME = "mexican"

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

    def mexican_standoff(self, message):
        reply = message.reply("points a pistol at %s." % message.user())
        reply['helper_metadata']['irc'] = {'irc_command': 'ACTION'}
        self.transport_publisher.publish_message(reply)

    def mexican_food(self, message):
        food = random.choice([
                "Nachos",
                "Tacos",
                "Quesadillas",
                "Burritos",
                "Tamales",
                ])
        return u"¡%s!" % food
