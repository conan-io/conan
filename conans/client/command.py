import argparse
import inspect
import sys
from argparse import ArgumentError
from difflib import get_close_matches

from conans.cli.exit_codes import SUCCESS, ERROR_GENERAL, ERROR_INVALID_CONFIGURATION, \
    ERROR_INVALID_SYSTEM_REQUIREMENTS
from conans.cli.output import ConanOutput
from conans.client.conan_api import ConanAPIV1
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.errors import ConanInvalidSystemRequirements
from conans.model.recipe_ref import RecipeReference
from conans.util.files import exception_message_safe
from conans.util.log import logger



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
        import textwrap
        text = textwrap.dedent(text)
        return ''.join(indent + line for line in text.splitlines(True))


_PATH_HELP = ("Path to a folder containing a conanfile.py or to a recipe file "
              "e.g., my_folder/conanfile.py")


class Command(object):
    """A single command of the conan application, with all the first level commands. Manages the
    parsing of parameters and delegates functionality in collaborators. It can also show the
    help of the tool.
    """
    def __init__(self, conan_api):
        assert isinstance(conan_api, ConanAPIV1)
        self._conan_api = conan_api
        self._out = ConanOutput()

    def source(self, *args):
        """
        Calls your local conanfile.py 'source()' method.

        Usually downloads and uncompresses the package sources.
        """
        parser = argparse.ArgumentParser(description=self.source.__doc__,
                                         prog="conan source",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("-sf", "--source-folder", action=OnceArgument,
                            help='Destination directory. Defaulted to current directory')
        args = parser.parse_args(*args)

        try:
            if "@" in args.path and RecipeReference.loads(args.path):
                raise ArgumentError(None,
                                    "'conan source' doesn't accept a reference anymore. "
                                    "If you were using it as a concurrency workaround, "
                                    "you can call 'conan install' simultaneously from several "
                                    "different processes, the concurrency is now natively supported"
                                    ". The path parameter should be a folder containing a "
                                    "conanfile.py file.")
        except ConanException:
            pass

        self._warn_python_version()
        return self._conan_api.source(args.path, args.source_folder)

    def _commands(self):
        """ Returns a list of available commands.
        """
        result = {}
        for m in inspect.getmembers(self, predicate=inspect.ismethod):
            method_name = m[0]
            if not method_name.startswith('_'):
                if "export_pkg" == method_name:
                    method_name = "export-pkg"
                method = m[1]
                if method.__doc__ and not method.__doc__.startswith('HIDDEN'):
                    result[method_name] = method
        return result

    def _print_similar(self, command):
        """ Looks for similar commands and prints them if found.
        """
        matches = get_close_matches(
            word=command, possibilities=self._commands().keys(), n=5, cutoff=0.75)

        if len(matches) == 0:
            return

        if len(matches) > 1:
            self._out.info("The most similar commands are")
        else:
            self._out.info("The most similar command is")

        for match in matches:
            self._out.info("    %s" % match)

        self._out.info("")

    def _warn_python_version(self):
        version = sys.version_info
        if version.major == 2 or  version.minor < 6:
            raise ConanException("Conan needs Python >= 3.6")

    def run(self, *args):
        """HIDDEN: entry point for executing commands, dispatcher to class
        methods
        """
        ret_code = SUCCESS
        try:
            command = args[0][0]
            commands = self._commands()
            method = commands[command]

            method(args[0][1:])
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
        except ConanInvalidSystemRequirements as exc:
            ret_code = ERROR_INVALID_SYSTEM_REQUIREMENTS
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
