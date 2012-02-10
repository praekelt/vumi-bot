# -*- test-case-name: tests.test_mexican -*-

"""
Stuff Mexicans do.
"""

from vumibot.base import BotWorker, botcommand


class MexicanWorker(BotWorker):
    FEATURE_NAME = "github"

    @botcommand(r'(?P<subcommand>\w*)!?')
    def cmd_mexican(self, message, params, subcommand):
        handler = getattr(self, 'mexican_%s' % subcommand, None)
        print handler
        if not handler:
            return "I don't think mexicans know how to do that."
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
