import importlib
import os
import pkgutil
import signal
import sys
import textwrap
from collections import defaultdict
from difflib import get_close_matches
from inspect import getmembers

from conan.api.conan_api import ConanAPI
from conan.api.output import ConanOutput, Color, cli_out_write
from conan.cli.command import ConanSubCommand
from conan.cli.exit_codes import SUCCESS, ERROR_MIGRATION, ERROR_GENERAL, USER_CTRL_C, \
    ERROR_SIGTERM, USER_CTRL_BREAK, ERROR_INVALID_CONFIGURATION, ERROR_INVALID_SYSTEM_REQUIREMENTS
from conans import __version__ as client_version
from conans.client.cache.cache import ClientCache
from conans.errors import ConanException, ConanInvalidConfiguration, ConanMigrationError
from conans.errors import ConanInvalidSystemRequirements
from conans.util.files import exception_message_safe


class Cli:
    """A single command of the conan application, with all the first level commands. Manages the
    parsing of parameters and delegates functionality to the conan python api. It can also show the
    help of the tool.
    """

    def __init__(self, conan_api):
        assert isinstance(conan_api, ConanAPI), \
            "Expected 'Conan' type, got '{}'".format(type(conan_api))
        self._conan_api = conan_api
        self._groups = defaultdict(list)
        self._commands = {}

    def _add_commands(self):
        conan_commands_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands")
        for module in pkgutil.iter_modules([conan_commands_path]):
            module_name = module[1]
            self._add_command("conan.cli.commands.{}".format(module_name), module_name)

        custom_commands_path = ClientCache(self._conan_api.cache_folder).custom_commands_path
        if not os.path.isdir(custom_commands_path):
            return

        sys.path.append(custom_commands_path)
        for module in pkgutil.iter_modules([custom_commands_path]):
            module_name = module[1]
            if module_name.startswith("cmd_"):
                try:
                    self._add_command(module_name, module_name.replace("cmd_", ""))
                except Exception as e:
                    ConanOutput().error("Error loading custom command "
                                        "'{}.py': {}".format(module_name, e))
        # layers
        for folder in os.listdir(custom_commands_path):
            layer_folder = os.path.join(custom_commands_path, folder)
            if not os.path.isdir(layer_folder):
                continue
            for module in pkgutil.iter_modules([layer_folder]):
                module_name = module[1]
                if module_name.startswith("cmd_"):
                    self._add_command(f"{folder}.{module_name}", module_name.replace("cmd_", ""),
                                      package=folder)

    def _add_command(self, import_path, method_name, package=None):
        try:
            imported_module = importlib.import_module(import_path)
            command_wrapper = getattr(imported_module, method_name)
            if command_wrapper.doc:
                name = f"{package}:{command_wrapper.name}" if package else command_wrapper.name
                self._commands[name] = command_wrapper
                self._groups[command_wrapper.group].append(name)
            for name, value in getmembers(imported_module):
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

    def _output_help_cli(self):
        """
        Prints a summary of all commands.
        """
        max_len = max((len(c) for c in self._commands)) + 1
        line_format = '{{: <{}}}'.format(max_len)

        for group_name, comm_names in sorted(self._groups.items()):
            cli_out_write(group_name + " commands", Color.BRIGHT_MAGENTA)
            for name in comm_names:
                # future-proof way to ensure tabular formatting
                cli_out_write(line_format.format(name), Color.GREEN, endline="")

                # Help will be all the lines up to the first empty one
                docstring_lines = self._commands[name].doc.split('\n')
                start = False
                data = []
                for line in docstring_lines:
                    line = line.strip()
                    if not line:
                        if start:
                            break
                        start = True
                        continue
                    data.append(line)

                txt = textwrap.fill(' '.join(data), 80, subsequent_indent=" " * (max_len + 2))
                cli_out_write(txt)

        cli_out_write("")
        cli_out_write('Conan commands. Type "conan <command> -h" for help', Color.BRIGHT_YELLOW)

    def run(self, *args):
        """ Entry point for executing commands, dispatcher to class
        methods
        """
        output = ConanOutput()
        try:
            self._add_commands()
            try:
                command_argument = args[0][0]
            except IndexError:  # No parameters
                self._output_help_cli()
                return SUCCESS
            try:
                command = self._commands[command_argument]
            except KeyError as exc:
                if command_argument in ["-v", "--version"]:
                    cli_out_write("Conan version %s" % client_version, fg=Color.BRIGHT_GREEN)
                    return SUCCESS

                if command_argument in ["-h", "--help"]:
                    self._output_help_cli()
                    return SUCCESS

                output.info("'%s' is not a Conan command. See 'conan --help'." % command_argument)
                output.info("")
                self._print_similar(command_argument)
                raise ConanException("Unknown command %s" % str(exc))
        except ConanException as exc:
            output.error(exc)
            return ERROR_GENERAL

        try:
            command.run(self._conan_api, self._commands[command_argument].parser, args[0][1:])
            exit_error = SUCCESS
        except SystemExit as exc:
            if exc.code != 0:
                output.error("Exiting with code: %d" % exc.code)
            exit_error = exc.code
        except ConanInvalidConfiguration as exc:
            exit_error = ERROR_INVALID_CONFIGURATION
            output.error(exc)
        except ConanInvalidSystemRequirements as exc:
            exit_error = ERROR_INVALID_SYSTEM_REQUIREMENTS
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

    try:
        conan_api = ConanAPI()
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
    exit_error = cli.run(args)

    sys.exit(exit_error)
