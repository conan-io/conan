import argparse
import os
import signal
import sys
import textwrap
from collections import defaultdict
from difflib import get_close_matches
import importlib
import pkgutil

from conans import __version__ as client_version
from conans.cli.exit_codes import SUCCESS, ERROR_MIGRATION, ERROR_GENERAL, USER_CTRL_C, \
    ERROR_SIGTERM, USER_CTRL_BREAK, ERROR_INVALID_CONFIGURATION
from conans.util.env_reader import get_env
from conans.client.conan_api import Conan
from conans.errors import ConanException, ConanInvalidConfiguration, ConanMigrationError
from conans.util.files import exception_message_safe
from conans.util.log import logger


class Extender(argparse.Action):
    """Allows using the same flag several times in command and creates a list with the values.
    For example:
        conan install MyPackage/1.2@user/channel -o qt:value -o mode:2 -s cucumber:true
      It creates:
          options = ['qt:value', 'mode:2']
          settings = ['cucumber:true']
    """

    def __call__(self, parser, namespace, values, option_strings=None):  # @UnusedVariable
        # Need None here incase `argparse.SUPPRESS` was supplied for `dest`
        dest = getattr(namespace, self.dest, None)
        if not hasattr(dest, 'extend') or dest == self.default:
            dest = []
            setattr(namespace, self.dest, dest)
            # if default isn't set to None, this method might be called
            # with the default as `values` for other arguments which
            # share this destination.
            parser.set_defaults(**{self.dest: None})

        if isinstance(values, str):
            dest.append(values)
        elif values:
            try:
                dest.extend(values)
            except ValueError:
                dest.append(values)


class OnceArgument(argparse.Action):
    """Allows declaring a parameter that can have only one value, by default argparse takes the
    latest declared and it's very confusing.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None and self.default is None:
            msg = '{o} can only be specified once'.format(o=option_string)
            raise argparse.ArgumentError(None, msg)
        setattr(namespace, self.dest, values)


class SmartFormatter(argparse.HelpFormatter):

    def _fill_text(self, text, width, indent):
        text = textwrap.dedent(text)
        return ''.join(indent + line for line in text.splitlines(True))


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
            self._out.writeln("The most similar commands are")
        else:
            self._out.writeln("The most similar command is")

        for match in matches:
            self._out.writeln("    %s" % match)

        self._out.writeln("")

    def help_message(self):
        self.commands["help"].method(conan_api=self.conan_api, parser=self.commands["help"].parser,
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
                self._out.success("Conan version %s" % client_version)
                return SUCCESS

            if command_argument in ["-h", "--help"]:
                self.help_message()
                return SUCCESS

            self._out.writeln(
                "'%s' is not a Conan command. See 'conan --help'." % command_argument)
            self._out.writeln("")
            self._print_similar(command_argument)
            raise ConanException("Unknown command %s" % str(exc))

        command.run(args[0][1:], conan_api=self.conan_api,
                    parser=self.commands[command_argument].parser,
                    commands=self.commands, groups=self.groups)

        return SUCCESS


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
        conan_api, _, _ = Conan.factory()  # FIXME: Conan factory will be removed in Conan 2.0
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

    cli = Cli(conan_api)

    try:
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
