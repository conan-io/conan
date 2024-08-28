import argparse
import os
import textwrap

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conans.model.conf import CORE_CONF_PATTERN


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


class BaseConanCommand:
    def __init__(self, method, formatters=None):
        self._formatters = {"text": lambda x: None}
        self._method = method
        self._name = None
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

    @staticmethod
    def _init_log_levels(parser):
        parser.add_argument("-v", default="status", nargs='?',
                            help="Level of detail of the output. Valid options from less verbose "
                                 "to more verbose: -vquiet, -verror, -vwarning, -vnotice, -vstatus, "
                                 "-v or -vverbose, -vv or -vdebug, -vvv or -vtrace")
        parser.add_argument("-cc", "--core-conf", action="append",
                            help="Define core configuration, overwriting global.conf "
                                 "values. E.g.: -cc core:non_interactive=True")

    @property
    def _help_formatters(self):
        """
        Formatters that are shown as available in help, 'text' formatter
        should not appear
        """
        return [formatter for formatter in self._formatters if formatter != "text"]

    def _init_formatters(self, parser):
        formatters = self._help_formatters
        if formatters:
            help_message = "Select the output format: {}".format(", ".join(formatters))
            parser.add_argument('-f', '--format', action=OnceArgument, help=help_message)

    @property
    def name(self):
        return self._name

    @property
    def method(self):
        return self._method

    @property
    def doc(self):
        return self._doc

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

    def _dispatch_errors(self, info):
        if info and isinstance(info, dict):
            if info.get("conan_error"):
                raise ConanException(info["conan_error"])
            if info.get("conan_warning"):
                ConanOutput().warning(info["conan_warning"])

class ConanArgumentParser(argparse.ArgumentParser):

    def __init__(self, conan_api, *args, **kwargs):
        self._conan_api = conan_api
        super().__init__(*args, **kwargs)

    def parse_args(self, args=None, namespace=None):
        args = super().parse_args(args)
        ConanOutput.define_log_level(os.getenv("CONAN_LOG_LEVEL", args.v))
        if getattr(args, "lockfile_packages", None):
            ConanOutput().error("The --lockfile-packages arg is private and shouldn't be used")
        if args.core_conf:
            from conans.model.conf import ConfDefinition
            confs = ConfDefinition()
            for c in args.core_conf:
                if not CORE_CONF_PATTERN.match(c):
                    raise ConanException(f"Only core. values are allowed in --core-conf. Got {c}")
            confs.loads("\n".join(args.core_conf))
            confs.validate()
            self._conan_api.config.global_conf.update_conf_definition(confs)
        return args


class ConanCommand(BaseConanCommand):
    def __init__(self, method, group=None, formatters=None):
        super().__init__(method, formatters=formatters)
        self._subcommands = {}
        self._group = group or "Other"
        self._name = method.__name__.replace("_", "-")

    def add_subcommand(self, subcommand):
        subcommand.set_name(self.name)
        self._subcommands[subcommand.name] = subcommand

    def run_cli(self, conan_api, *args):
        parser = ConanArgumentParser(conan_api, description=self._doc,
                                     prog="conan {}".format(self._name),
                                     formatter_class=SmartFormatter)
        self._init_log_levels(parser)
        self._init_formatters(parser)
        info = self._method(conan_api, parser, *args)
        if not self._subcommands:
            return info

        subcommand_parser = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subcommand_parser.required = True

        subcmd = args[0][0]
        try:
            sub = self._subcommands[subcmd]
        except (KeyError, IndexError):  # display help
            raise ConanException(f"Sub command {subcmd} does not exist")
        else:
            sub.set_parser(subcommand_parser, conan_api)
            return sub.run_cli(conan_api, parser, *args)

    def run(self, conan_api, *args):
        parser = ConanArgumentParser(conan_api, description=self._doc,
                                     prog="conan {}".format(self._name),
                                     formatter_class=SmartFormatter)
        self._init_log_levels(parser)
        self._init_formatters(parser)

        info = self._method(conan_api, parser, *args)

        if not self._subcommands:
            self._format(parser, info, *args)
        else:
            subcommand_parser = parser.add_subparsers(dest='subcommand', help='sub-command help')
            subcommand_parser.required = True

            try:
                sub = self._subcommands[args[0][0]]
            except (KeyError, IndexError):  # display help
                for sub in self._subcommands.values():
                    sub.set_parser(subcommand_parser, conan_api)
                parser.parse_args(*args)
            else:
                sub.set_parser(subcommand_parser, conan_api)
                sub.run(conan_api, parser, *args)
        self._dispatch_errors(info)

    @property
    def group(self):
        return self._group


class ConanSubCommand(BaseConanCommand):
    def __init__(self, method, formatters=None):
        super().__init__(method, formatters=formatters)
        self._parser = None
        self._subcommand_name = method.__name__.replace('_', '-')

    def run_cli(self, conan_api, parent_parser, *args):
        return self._method(conan_api, parent_parser, self._parser, *args)

    def run(self, conan_api, parent_parser, *args):
        info = self._method(conan_api, parent_parser, self._parser, *args)
        # It is necessary to do it after calling the "method" otherwise parser not complete
        self._format(parent_parser, info, *args)
        self._dispatch_errors(info)

    def set_name(self, parent_name):
        self._name = self._subcommand_name.replace(f'{parent_name}-', '', 1)

    def set_parser(self, subcommand_parser, conan_api):
        self._parser = subcommand_parser.add_parser(self._name, conan_api=conan_api, help=self._doc)
        self._parser.description = self._doc
        self._init_formatters(self._parser)
        self._init_log_levels(self._parser)


def conan_command(group=None, formatters=None):
    return lambda f: ConanCommand(f, group, formatters=formatters)


def conan_subcommand(formatters=None):
    return lambda f: ConanSubCommand(f, formatters=formatters)
