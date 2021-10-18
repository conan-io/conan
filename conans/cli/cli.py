import importlib
import os
import pkgutil
import signal
import sys
from collections import defaultdict
from difflib import get_close_matches
from inspect import getmembers

from conans import __version__ as client_version
from conans.cli.api.conan_api import ConanAPIV2, ConanAPI
from conans.cli.command import ConanSubCommand
from conans.cli.exit_codes import SUCCESS, ERROR_MIGRATION, ERROR_GENERAL, USER_CTRL_C, \
    ERROR_SIGTERM, USER_CTRL_BREAK, ERROR_INVALID_CONFIGURATION
from conans.cli.output import ConanOutput
from conans.client.command import Command
from conans.client.conan_api import ConanAPIV1
from conans.client.conf.config_installer import is_config_install_scheduled
from conans.errors import ConanException, ConanInvalidConfiguration, ConanMigrationError
from conans.util.files import exception_message_safe
from conans.util.log import logger


CLI_V1_COMMANDS = [
    'install', 'config', 'get', 'info', 'new', 'create', 'upload', 'export', 'export-pkg',
    'test', 'source', 'build', 'editable', 'profile', 'imports', 'remove', 'alias',
    'download', 'inspect', 'lock', 'frogarian', 'graph'
]


class Cli(object):
    """A single command of the conan application, with all the first level commands. Manages the
    parsing of parameters and delegates functionality to the conan python api. It can also show the
    help of the tool.
    """

    def __init__(self, conan_api):
        assert isinstance(conan_api, (ConanAPIV1, ConanAPIV2)), \
            "Expected 'Conan' type, got '{}'".format(type(conan_api))
        self._conan_api = conan_api
        self._groups = defaultdict(list)
        self._commands = {}
        conan_commands_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands")
        for module in pkgutil.iter_modules([conan_commands_path]):
            module_name = module[1]
            self._add_command("conans.cli.commands.{}".format(module_name), module_name)
        user_commands_path = os.path.join(self._conan_api.cache_folder, "commands")
        sys.path.append(user_commands_path)
        for module in pkgutil.iter_modules([user_commands_path]):
            module_name = module[1]
            if module_name.startswith("cmd_"):
                self._add_command(module_name, module_name.replace("cmd_", ""))

    def _add_command(self, import_path, method_name):
        try:
            command_wrapper = getattr(importlib.import_module(import_path), method_name)
            if command_wrapper.doc:
                self._commands[command_wrapper.name] = command_wrapper
                self._groups[command_wrapper.group].append(command_wrapper.name)
            for name, value in getmembers(importlib.import_module(import_path)):
                if isinstance(value, ConanSubCommand):
                    if name.startswith("{}_".format(method_name)):
                        command_wrapper.add_subcommand(value)
                    else:
                        raise ConanException("The name for the subcommand method should "
                                             "begin with the main command name + '_'. "
                                             "i.e. {}_<subcommand_name>".format(method_name))
        except AttributeError:
            raise ConanException("There is no {} method defined in {}".format(method_name,
                                                                              import_path))

    def _print_similar(self, command):
        """ Looks for similar commands and prints them if found.
        """
        output = ConanOutput()
        matches = get_close_matches(
            word=command, possibilities=self._commands.keys(), n=5, cutoff=0.75)

        if len(matches) == 0:
            return

        if len(matches) > 1:
            output.info("The most similar commands are")
        else:
            output.info("The most similar command is")

        for match in matches:
            output.info("    %s" % match)

        output.writeln("")

    def help_message(self):
        self._commands["help"].method(self._conan_api, self._commands["help"].parser,
                                      commands=self._commands, groups=self._groups)

    def run(self, *args):
        """ Entry point for executing commands, dispatcher to class
        methods
        """
        output = ConanOutput()
        version = sys.version_info
        if version.major == 2 or version.minor <= 4:
            raise ConanException(
                "Unsupported Python version. Minimum required version is Python 3.5")
        try:
            try:
                command_argument = args[0][0]
            except IndexError:  # No parameters
                self.help_message()
                return SUCCESS
            try:
                command = self._commands[command_argument]
            except KeyError as exc:
                if command_argument in ["-v", "--version"]:
                    output.info("Conan version %s" % client_version)
                    return SUCCESS

                if command_argument in ["-h", "--help"]:
                    self.help_message()
                    return SUCCESS

                output.info("'%s' is not a Conan command. See 'conan --help'." % command_argument)
                output.info("")
                self._print_similar(command_argument)
                raise ConanException("Unknown command %s" % str(exc))
        except ConanException as exc:
            output.error(exc)
            return ERROR_GENERAL

        if (
            command != "config"
            or (
                command == "config" and len(args[0]) > 1 and args[0][1] != "install"
            )
        ) and is_config_install_scheduled(self._conan_api):
            self._conan_api.config_install(None, None)

        try:
            command.run(self._conan_api, self._commands[command_argument].parser,
                        args[0][1:], commands=self._commands, groups=self._groups)
            exit_error = SUCCESS
        except SystemExit as exc:
            if exc.code != 0:
                logger.error(exc)
                output.error("Exiting with code: %d" % exc.code)
            exit_error = exc.code
        except ConanInvalidConfiguration as exc:
            exit_error = ERROR_INVALID_CONFIGURATION
            output.error(exc)
        except ConanException as exc:
            exit_error = ERROR_GENERAL
            output.error(exc)
        except Exception as exc:
            import traceback
            print(traceback.format_exc())
            exit_error = ERROR_GENERAL
            msg = exception_message_safe(exc)
            output.error(msg)

        return exit_error


def main(args):
    """ main entry point of the conan application, using a Command to
    parse parameters

    Exit codes for conan command:

        0: Success (done)
        1: General ConanException error (done)
        2: Migration error
        3: Ctrl+C
        4: Ctrl+Break
        5: SIGTERM
        6: Invalid configuration (done)
    """

    # Temporary hack to call the legacy command system if the command is not yet implemented in V2
    command_argument = args[0] if args else None
    is_v1_command = command_argument in CLI_V1_COMMANDS

    try:
        conan_api = ConanAPIV1() if is_v1_command else ConanAPI()
    except ConanMigrationError:  # Error migrating
        sys.exit(ERROR_MIGRATION)
    except ConanException as e:
        sys.stderr.write("Error in Conan initialization: {}".format(e))
        sys.exit(ERROR_GENERAL)

    def ctrl_c_handler(_, __):
        print('You pressed Ctrl+C!')
        sys.exit(USER_CTRL_C)

    def sigterm_handler(_, __):
        print('Received SIGTERM!')
        sys.exit(ERROR_SIGTERM)

    def ctrl_break_handler(_, __):
        print('You pressed Ctrl+Break!')
        sys.exit(USER_CTRL_BREAK)

    signal.signal(signal.SIGINT, ctrl_c_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)

    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, ctrl_break_handler)

    if is_v1_command:
        command = Command(conan_api)
        exit_error = command.run(args)
    else:
        cli = Cli(conan_api)
        exit_error = cli.run(args)

    sys.exit(exit_error)
