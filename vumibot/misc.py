# -*- test-case-name: tests.test_misc -*-

"""
Miscellaneous miscellanea.
"""

from vumibot.base import BotWorker, botcommand


class MiscWorker(BotWorker):
    FEATURE_NAME = "misc"

    @botcommand
    def cmd_ping(self, message, params):
        return "pong."
