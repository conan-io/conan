from conan.api.output import ConanOutput
from conan.errors import ConanException


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
        # Conan has some global state in the ConanOutput class that
        # get redefined when running a command and leak to the calling scope
        # if running from a custom command.
        # Store the old one and restore it after the command execution as a workaround.
        _conan_output_level = ConanOutput._conan_output_level
        _silent_warn_tags = ConanOutput._silent_warn_tags
        _warnings_as_errors = ConanOutput._warnings_as_errors

        try:
            result = command.run_cli(self.conan_api, args)
        finally:
            ConanOutput._conan_output_level = _conan_output_level
            ConanOutput._silent_warn_tags = _silent_warn_tags
            ConanOutput._warnings_as_errors = _warnings_as_errors
        return result
