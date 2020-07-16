import argparse

from conans.cli.cli import SmartFormatter, OnceArgument
from conans.errors import ConanException


class ConanCommand(object):
    def __init__(self, method, group, formatters=None, subcommands=None):
        self._formatters = {}
        self._subparsers = None
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

        subcommands_names = []
        if subcommands:
            self._subcommand_parser = self._parser.add_subparsers(dest='subcommand',
                                                                  help='sub-command help')
            self._subcommand_parser.required = True
            self._subparsers = {}
            for subcommand in subcommands:
                try:
                    self._subparsers[subcommand["name"]] = self._subcommand_parser.add_parser(
                        subcommand["name"],
                        help=subcommand["help"])
                    subcommands_names.append(subcommand["name"])
                except KeyError:
                    raise ConanException("Both 'name' and 'help' should be defined when adding "
                                         "subcommands.")
            for subcommand_name in subcommands_names:
                if formatters.get(subcommand_name, None):
                    self._formatters[subcommand_name] = {}
                    for kind, action in formatters[subcommand_name].items():
                        if callable(action):
                            self._formatters[subcommand_name][kind] = action
                        else:
                            raise ConanException("Invalid formatter for {} in sub-command: '{}'. The "
                                                 "formatter must be a valid function".format(kind,
                                                                                             subcommand_name))
            if self._formatters:
                for subcommmand, formatters_dict in self._formatters.items():
                    formatters_list = list(formatters_dict.keys())
                    default_output = "cli" if "cli" in formatters_list else formatters_list[0]
                    output_help_message = "Select the output format: {}. '{}' is the default output." \
                        .format(", ".join(formatters_list), default_output)
                    self._subparsers[subcommmand].add_argument('-o', '--output',
                                                                      default=default_output,
                                                                      choices=formatters_list,
                                                                      action=OnceArgument,
                                                                      help=output_help_message)

        if not self._formatters:
            for kind, action in formatters.items():
                if callable(action):
                    self._formatters[kind] = action
                else:
                    raise ConanException("Invalid formatter for {}. The formatter must be"
                                         "a valid function".format(kind))
            if self._formatters:
                formatters_list = list(self._formatters.keys())
                default_output = "cli" if "cli" in formatters_list else formatters_list[0]
                output_help_message = "Select the output format: {}. '{}' is the default output." \
                    .format(", ".join(formatters_list), default_output)
                self._parser.add_argument('-o', '--output', default=default_output,
                                          choices=formatters_list,
                                          action=OnceArgument, help=output_help_message)

    def run(self, conan_api, *args, **kwargs):
        try:
            info = self._method(*args, conan_api=conan_api, **kwargs)
            parser_args = self._parser.parse_args(*args)
            if info:
                if not self._subparsers:
                    self._formatters[parser_args.output](info, conan_api.out)
                else:
                    self._formatters[parser_args.subcommand][parser_args.output](info, conan_api.out)
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

    @property
    def subparsers(self):
        return self._subparsers


def conan_command(group, formatters=None, subcommands=None):
    def decorator(f):
        cmd = ConanCommand(f, group, formatters, subcommands)
        return cmd

    return decorator
