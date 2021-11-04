from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.commands import json_formatter
from conans.cli.output import ConanOutput

list_package_ids_formatters = {
    "json": json_formatter
}


def profiles_output(profiles):
    host, build = profiles
    output = ConanOutput()
    output.writeln("Host profile:")
    output.writeln(host.dumps())
    output.writeln("Build profile:")
    output.writeln(build.dumps())


def add_profiles_args(parser):

    def profile_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-pr{}".format(short_suffix),
                            "--profile{}".format(long_suffix),
                            default=None, action=Extender,
                            dest='profile_{}'.format(machine),
                            help='Apply the specified profile to the {} machine'.format(machine))

    def settings_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-s{}".format(short_suffix),
                            "--settings{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest='settings_{}'.format(machine),
                            help='Settings to build the package, overwriting the defaults'
                                 ' ({} machine). e.g.: -s{} compiler=gcc'.format(machine,
                                                                                 short_suffix))

    def options_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-o{}".format(short_suffix),
                            "--options{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest="options_{}".format(machine),
                            help='Define options values ({} machine), e.g.:'
                                 ' -o{} Pkg:with_qt=true'.format(machine, short_suffix))

    def conf_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-c{}".format(short_suffix),
                            "--conf{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest='conf_{}'.format(machine),
                            help='Configuration to build the package, overwriting the defaults'
                                 ' ({} machine). e.g.: -c{} '
                                 'tools.cmake.cmaketoolchain:generator=Xcode'.format(machine,
                                                                                     short_suffix))

    for item_fn in [options_args, profile_args, settings_args, conf_args]:
        item_fn("host", "",
                "")  # By default it is the HOST, the one we are building binaries for
        item_fn("build", ":b", ":build")
        item_fn("host", ":h", ":host")


@conan_subcommand(formatters={"cli": profiles_output})
def profile_show(conan_api, parser, subparser, *args):
    """
    Show profiles
    """
    add_profiles_args(subparser)
    args = parser.parse_args(*args)
    profile_build = conan_api.profiles.get_profile(profiles=args.profile_build,
                                                   settings=args.settings_build,
                                                   options=args.options_build,
                                                   conf=args.conf_build, build_profile=True)
    profile_host = conan_api.profiles.get_profile(profiles=args.profile_host,
                                                  settings=args.settings_host,
                                                  options=args.options_host,
                                                  conf=args.conf_host)
    return profile_host, profile_build


@conan_subcommand(formatters=list_package_ids_formatters)
def profile_detect(conan_api, parser, subparser, *args):
    """
    Detect default profile
    """
    subparser.add_argument("--name", help="Profile name, 'default' if not specified")
    subparser.add_argument("--force", action='store_true', help="Overwrite if exists")
    args = parser.parse_args(*args)

    result = conan_api.profiles.detect_profile(args.name, args.force)
    return result


@conan_subcommand(formatters=list_package_ids_formatters)
def profile_list(conan_api, parser, subparser, *args):
    """
    List all profiles in the cache
    """
    return conan_api.profiles.list()


@conan_command(group=COMMAND_GROUPS['consumer'])
def profile(conan_api, parser, *args, **kwargs):
    """
    Manage profiles
    """
