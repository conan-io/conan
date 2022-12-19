import argparse
import textwrap

from conan.cli.commands import add_log_level_args, process_log_level_args
from conans.errors import ConanException


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


class BaseConanCommand(object):
    def __init__(self, method, formatters=None):
        self._formatters = {"text": lambda x: None}
        self._method = method
        self._name = None
        self._parser = None
        if formatters:
            for kind, action in formatters.items():
                if callable(action):
                    self._formatters[kind] = action
                else:
                    raise ConanException("Invalid formatter for {}. The formatter must be"
                                         "a valid function".format(kind))
        if method.__doc__:
            self._doc = method.__doc__
        else:
            raise ConanException("No documentation string defined for command: '{}'. Conan "
                                 "commands should provide a documentation string explaining "
                                 "its use briefly.".format(self._name))

    def _init_log_levels(self):
        add_log_level_args(self._parser)

    @property
    def _help_formatters(self):
        """
        Formatters that are shown as available in help, 'text' formatter
        should not appear
        """
        return [formatter for formatter in list(self._formatters) if formatter != "text"]

    def _init_formatters(self):
        if self._help_formatters:
            help_message = "Select the output format: {}".format(", ".join(list(self._help_formatters)))
            self._parser.add_argument('-f', '--format', action=OnceArgument, help=help_message)

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

    def _format(self, parser, info, *args):
        parser_args, _ = parser.parse_known_args(*args)

        default_format = "text"
        try:
            formatarg = parser_args.format or default_format
        except AttributeError:
            formatarg = default_format

        try:
            formatter = self._formatters[formatarg]
        except KeyError:
            raise ConanException("{} is not a known format. Supported formatters are: {}".format(
                formatarg, ", ".join(self._help_formatters)))

        formatter(info)


class ConanArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def parse_args(self, args=None, namespace=None):
        args = super().parse_args(args)
        process_log_level_args(args)
        return args


class ConanCommand(BaseConanCommand):
    def __init__(self, method, group=None, formatters=None):
        super().__init__(method, formatters=formatters)
        self._subcommands = {}
        self._subcommand_parser = None
        self._group = group or "Other"
        self._name = method.__name__.replace("_", "-")
        self._parser = ConanArgumentParser(description=self._doc,
                                           prog="conan {}".format(self._name),
                                           formatter_class=SmartFormatter)
        self._init_formatters()
        self._init_log_levels()

    def add_subcommand(self, subcommand):
        if not self._subcommand_parser:
            self._subcommand_parser = self._parser.add_subparsers(dest='subcommand',
                                                                  help='sub-command help')
            self._subcommand_parser.required = True
        subcommand.set_parser(self._parser, self._subcommand_parser)
        self._subcommands[subcommand.name] = subcommand

    def run(self, conan_api, parser, *args):
        info = self._method(conan_api, parser, *args)

        if not self._subcommands:
            self._format(self._parser, info, *args)
        else:
            subcommand = args[0][0] if args[0] else None
            if subcommand in self._subcommands:
                self._subcommands[subcommand].run(conan_api, *args)
            else:
                self._parser.parse_args(*args)

    @property
    def group(self):
        return self._group


class ConanSubCommand(BaseConanCommand):
    def __init__(self, method, formatters=None):
        super().__init__(method, formatters=formatters)
        self._parent_parser = None
        self._parser = None
        self._name = "-".join(method.__name__.split("_")[1:])

    def run(self, conan_api, *args):
        info = self._method(conan_api, self._parent_parser, self._parser, *args)
        # It is necessary to do it after calling the "method" otherwise parser not complete
        self._format(self._parent_parser, info, *args)

    def set_parser(self, parent_parser, subcommand_parser):
        self._parser = subcommand_parser.add_parser(self._name, help=self._doc)
        self._parser.description = self._doc
        self._parent_parser = parent_parser
        self._init_formatters()
        self._init_log_levels()


def conan_command(group=None, formatters=None):
    return lambda f: ConanCommand(f, group, formatters=formatters)


def conan_subcommand(formatters=None):
    return lambda f: ConanSubCommand(f, formatters=formatters)
