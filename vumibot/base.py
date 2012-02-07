import re


class CommandFormatException(Exception):
    pass


class BotCommand(object):

    def start_command(self):
        pass

    def stop_command(self):
        pass

    def get_command(self):
        raise NotImplementedError("Subclasses should implement this.")

    def get_pattern(self):
        raise NotImplementedError("Subclasses should implement this.")

    def get_compiled_pattern(self):
        if not hasattr(self, '_pattern'):
            self._pattern = re.compile(self.get_pattern(), re.VERBOSE)
        return self._pattern

    def get_help(self):
        return "I grok %s" % (self.get_pattern(),)

    def accepts(self, command):
        return command == self.get_command()

    def handle_command(self, user_id, command_text):
        raise NotImplementedError('Subclasses must implement handle_command()')

    def parse(self, user_id, full_text):
        try:
            command, command_text = full_text.split(' ', 1)
        except ValueError:
            command = full_text
            command_text = ''

        if self.accepts(command):
            return self.handle_command(user_id, command_text)
