from conans.errors import ConanException


class CommandAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api
        self.cli = None

    def run(self, *args):
        item, *args = args
        commands = self.cli._commands
        try:
            command = commands[item]
        except KeyError:
            raise ConanException(f"Command {item} does not exist")

        return command.run_cli(self.conan_api, *args)
