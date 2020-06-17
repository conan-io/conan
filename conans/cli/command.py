import argparse
import inspect
import os
import signal
import sys
import textwrap
from difflib import get_close_matches
import importlib
import pkgutil

from conans import __version__ as client_version
from conans.client.api.conan_api import Conan
from conans.client.output import Color
from conans.errors import ConanException, ConanInvalidConfiguration, ConanMigrationError
from conans.util.files import exception_message_safe
from conans.util.log import logger

# Exit codes for conan command:
SUCCESS = 0  # 0: Success (done)
ERROR_GENERAL = 1  # 1: General ConanException error (done)
ERROR_MIGRATION = 2  # 2: Migration error
USER_CTRL_C = 3  # 3: Ctrl+C
USER_CTRL_BREAK = 4  # 4: Ctrl+Break
ERROR_SIGTERM = 5  # 5: SIGTERM
ERROR_INVALID_CONFIGURATION = 6  # 6: Invalid configuration (done)


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


class ConanCommand(object):
    def __init__(self, method, group=None):
        self._group = group if group is not None else "Misc commands"
        self._name = method.__name__.replace("_", "-")
        self._method = method
        self._doc = method.__doc__

    @property
    def group(self):
        return self._group

    @property
    def name(self):
        return self._name

    @property
    def method(self):
        return self._method

    @property
    def doc(self):
        return self._doc


def conan_command(group=None):
    def decorator(f):
        cmd = ConanCommand(f, group)
        return cmd

    return decorator


class Command(object):
    """A single command of the conan application, with all the first level commands. Manages the
    parsing of parameters and delegates functionality to the conan python api. It can also show the
    help of the tool.
    """

    def __init__(self, conan_api):
        assert isinstance(conan_api, Conan)
        self._conan = conan_api
        self._out = conan_api.out
        self._groups = {}
        self._commands = {}

        conan_commands_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands")
        for module in pkgutil.iter_modules([conan_commands_path]):
            self._add_command("conans.cli.commands.{}".format(module.name), module.name)

        user_commands_path = os.path.join(self._conan.cache_folder, "commands")
        sys.path.append(user_commands_path)
        for module in pkgutil.iter_modules([user_commands_path]):
            if module.name.startswith("cmd_"):
                self._add_command(module.name, module.name.replace("cmd_", ""))

    def _add_command(self, import_path, method_name):
        command_wrapper = getattr(importlib.import_module(import_path), method_name)
        if command_wrapper.doc:
            self._commands[command_wrapper.name] = command_wrapper
            self._groups.setdefault(command_wrapper.group, []).append(command_wrapper.name)

    @property
    def conan_api(self):
        return self._conan

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
        self.commands["help"].method(self.conan_api, self.commands, self.groups)

    def run(self, *args):
        """ Entry point for executing commands, dispatcher to class
        methods
        """
        version = sys.version_info
        if version.major == 2 or version.minor <= 4:
            raise ConanException("Unsupported Python version")

        ret_code = SUCCESS
        try:
            try:
                command = args[0][0]
            except IndexError:  # No parameters
                self.help_message()
                return False
            try:
                method = self.commands[command].method
            except KeyError as exc:
                if command in ["-v", "--version"]:
                    self._out.success("Conan version %s" % client_version)
                    return False

                if command in ["-h", "--help"]:
                    self.help_message()
                    return False

                self._out.writeln("'%s' is not a Conan command. See 'conan --help'." % command)
                self._out.writeln("")
                self._print_similar(command)
                raise ConanException("Unknown command %s" % str(exc))

            method(self.conan_api, self.commands, self.groups,
                   args[0][1:]) if command == "help" else method(self.conan_api, args[0][1:])
        except KeyboardInterrupt as exc:
            logger.error(exc)
            ret_code = SUCCESS
        except SystemExit as exc:
            if exc.code != 0:
                logger.error(exc)
                self._out.error("Exiting with code: %d" % exc.code)
            ret_code = exc.code
        except ConanInvalidConfiguration as exc:
            ret_code = ERROR_INVALID_CONFIGURATION
            self._out.error(exc)
        except ConanException as exc:
            ret_code = ERROR_GENERAL
            self._out.error(exc)
        except Exception as exc:
            import traceback
            print(traceback.format_exc())
            ret_code = ERROR_GENERAL
            msg = exception_message_safe(exc)
            self._out.error(msg)

        return ret_code


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
        conan_api, _, _ = Conan.factory()
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

    command = Command(conan_api)
    error = command.run(args)
    sys.exit(error)
