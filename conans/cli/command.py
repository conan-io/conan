import argparse
import textwrap

from conans.cli.output import cli_out_write
from conans.errors import ConanException

COMMAND_GROUPS = {
    'consumer': 'Consumer commands',
    'misc': 'Miscellaneous commands',
    'creator': 'Creator commands'
}


class Extender(argparse.Action):
    """Allows using the same flag several times in command and creates a list with the values.
    For example:
        conan install MyPackage/1.2@user/channel -o qt/*:value -o mode/*:2 -s cucumber/*:true
      It creates:
          options = ['qt:value', 'mode:2']
          settings = ['cucumber:true']
    """
    raise_if_none = False

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
        else:  # When "--argument" with no value is specified
            if self.raise_if_none:
                raise argparse.ArgumentError(None, 'Specify --build="*" instead of --build')


class ExtenderValueRequired(Extender):

    # If --build is specified, it will raise
    raise_if_none = True


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
        self._formatters = {}
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

    def _init_formatters(self):
        if self._formatters:
            help_message = "Select the output format: {}".format(", ".join(list(self._formatters)))
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
        try:
            formatarg = parser_args.format
        except AttributeError:
            return

        if formatarg is None:
            return

        try:
            formatter = self._formatters[formatarg]
        except KeyError:
            raise ConanException("{} is not a known format: {}".format(formatarg,
                                                                       list(self._formatters)))

        if info is None:
            raise ConanException(f"Format {formatarg} was specified, but command didn't return "
                                 "anything to format")
        result = formatter(info)
        cli_out_write(result, endline="")


class ConanCommand(BaseConanCommand):
    def __init__(self, method, group=None, formatters=None):
        super().__init__(method, formatters=formatters)
        self._subcommands = {}
        self._subcommand_parser = None
        self._group = group or COMMAND_GROUPS['misc']
        self._name = method.__name__.replace("_", "-")
        self._parser = argparse.ArgumentParser(description=self._doc,
                                               prog="conan {}".format(self._name),
                                               formatter_class=SmartFormatter)
        self._init_formatters()

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
        self._parent_parser = parent_parser
        self._init_formatters()


def conan_command(group=None, formatters=None):
    def decorator(f):
        cmd = ConanCommand(f, group, formatters=formatters)
        return cmd

    return decorator


def conan_subcommand(formatters=None):
    def decorator(f):
        cmd = ConanSubCommand(f, formatters=formatters)
        return cmd

    return decorator
