# -*- test-case-name: tests.test_misc -*-

"""
Miscellaneous miscellanea.
"""

from vumibot.base import BotMessageProcessor, botcommand


class MiscMessageProcessor(BotMessageProcessor):
    @botcommand
    def cmd_ping(self, message, params):
        return "pong."
