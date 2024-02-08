from conans.errors import ConanException


class CliAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api
        self.cli = None

    def __getattr__(self, item):
        commands = self.cli._commands
        try:
            command = commands[item]
        except KeyError:
            raise ConanException(f"Command {item} does not exist")

        def wrapper(*args):
            return command.run_cli(self.conan_api, *args)
        return wrapper
