from conans.errors import ConanException


class CommandAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api
        self.cli = None

    def run(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.split()
        if isinstance(cmd, list):
            current_cmd = cmd[0]
            args = cmd[1:]
        else:
            raise ConanException("Input of conan_api.command.run() should be a list or a string")
        commands = getattr(self.cli, "_commands")  # to no make it public to users of Cli class
        try:
            command = commands[current_cmd]
        except KeyError:
            raise ConanException(f"Command {current_cmd} does not exist")

        return command.run_cli(self.conan_api, args)
