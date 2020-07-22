import argparse

from conans.cli.cli import SmartFormatter, OnceArgument
from conans.errors import ConanException


class ConanCommand(object):
    def __init__(self, method, group, formatters=None):
        self._formatters = {}
        for kind, action in formatters.items():
            if callable(action):
                self._formatters[kind] = action
            else:
                raise ConanException("Invalid formatter for {}. The formatter must be"
                                     "a valid function".format(kind))

        self._group = group or "Misc commands"
        self._name = method.__name__.replace("_", "-")
        self._method = method
        if method.__doc__:
            self._doc = method.__doc__
        else:
            raise ConanException("No documentation string defined for command: '{}'. Conan "
                                 "commands should provide a documentation string explaining "
                                 "its use briefly.".format(self._name))
        self._parser = argparse.ArgumentParser(description=self._doc,
                                               prog="conan {}".format(self._name),
                                               formatter_class=SmartFormatter)
        if self._formatters:
            formatters_list = list(self._formatters.keys())
            default_output = "cli" if "cli" in formatters_list else formatters_list[0]
            self._output_help_message = "Select the output format: {}. '{}' is the default output."\
                .format(", ".join(formatters_list), default_output)
            self._parser.add_argument('-o', '--output', default=default_output, choices=formatters_list,
                                      action=OnceArgument, help=self._output_help_message)

    def run(self, *args, conan_api, **kwargs):
        try:
            info = self._method(*args, conan_api=conan_api, **kwargs)
            parser_args = self._parser.parse_args(*args)
            if info:
                self._formatters[parser_args.output](info, conan_api.out)
        except Exception:
            raise

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

    @property
    def parser(self):
        return self._parser


def conan_command(group, formatters=None):
    def decorator(f):
        cmd = ConanCommand(f, group, formatters)
        return cmd

    return decorator
