import importlib
import os
import pkgutil
import signal
import sys
from collections import defaultdict
from difflib import get_close_matches
from inspect import getmembers

from colorama import Style

from conans import __version__ as client_version
from conans.cli.command import ConanSubCommand
from conans.cli.exit_codes import SUCCESS, ERROR_MIGRATION, ERROR_GENERAL, USER_CTRL_C, \
    ERROR_SIGTERM, USER_CTRL_BREAK, ERROR_INVALID_CONFIGURATION
from conans.client.api.conan_api import Conan
from conans.errors import ConanException, ConanInvalidConfiguration, ConanMigrationError
from conans.util.files import exception_message_safe
from conans.util.log import logger


class Cli(object):
    """A single command of the conan application, with all the first level commands. Manages the
    parsing of parameters and delegates functionality to the conan python api. It can also show the
    help of the tool.
    """

    def __init__(self, conan_api):
        assert isinstance(conan_api, Conan), "Expected 'Conan' type, got '{}'".format(
            type(conan_api))
        self._conan_api = conan_api
        self._out = conan_api.out
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

    @property
    def conan_api(self):
        return self._conan_api

    @property
    def commands(self):
        return self._commands

    @property
    def groups(self):
        return self._groups

    def _print_similar(self, command):
        """ Looks for similar commands and prints them if found.
        """
        matches = get_close_matches(
            word=command, possibilities=self.commands.keys(), n=5, cutoff=0.75)

        if len(matches) == 0:
            return

        if len(matches) > 1:
            self._out.info("The most similar commands are")
        else:
            self._out.info("The most similar command is")

        for match in matches:
            self._out.info("    %s" % match)

        self._out.info("")

    def help_message(self):
        self.commands["help"].method(self.conan_api, self.commands["help"].parser,
                                     commands=self.commands, groups=self.groups)

    def run(self, *args):
        """ Entry point for executing commands, dispatcher to class
        methods
        """
        version = sys.version_info
        if version.major == 2 or version.minor <= 4:
            raise ConanException(
                "Unsupported Python version. Minimum required version is Python 3.5")

        try:
            command_argument = args[0][0]
        except IndexError:  # No parameters
            self.help_message()
            return SUCCESS
        try:
            command = self.commands[command_argument]
        except KeyError as exc:
            if command_argument in ["-v", "--version"]:
                self._out.info("Conan version %s" % client_version)
                return SUCCESS

            if command_argument in ["-h", "--help"]:
                self.help_message()
                return SUCCESS

            self._out.info("'%s' is not a Conan command. See 'conan --help'." % command_argument)
            self._out.info("")
            self._print_similar(command_argument)
            raise ConanException("Unknown command %s" % str(exc))

        command.run(self.conan_api, self.commands[command_argument].parser,
                    args[0][1:], commands=self.commands, groups=self.groups)

        return SUCCESS


def cli_out_write(data, fg=None, bg=None):
    data = "{}{}{}{}\n".format(fg or '', bg or '', data, Style.RESET_ALL)
    sys.stdout.write(data)


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
    try:
        conan_api = Conan(quiet=False)
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

    try:
        cli = Cli(conan_api)
        exit_error = cli.run(args)
    except SystemExit as exc:
        if exc.code != 0:
            logger.error(exc)
            conan_api.out.error("Exiting with code: %d" % exc.code)
        exit_error = exc.code
    except ConanInvalidConfiguration as exc:
        exit_error = ERROR_INVALID_CONFIGURATION
        conan_api.out.error(exc)
    except ConanException as exc:
        exit_error = ERROR_GENERAL
        conan_api.out.error(exc)
    except Exception as exc:
        import traceback
        print(traceback.format_exc())
        exit_error = ERROR_GENERAL
        msg = exception_message_safe(exc)
        conan_api.out.error(msg)

    sys.exit(exit_error)
