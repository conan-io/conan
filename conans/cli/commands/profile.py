import os

from conans.cli.command import conan_command, conan_subcommand, Extender, COMMAND_GROUPS
from conans.cli.commands import json_formatter
from conans.cli.output import cli_out_write, ConanOutput
from conans.errors import ConanException
from conans.util.files import save


def profiles_cli_output(profiles):
    host, build = profiles
    cli_out_write("Host profile:")
    cli_out_write(host.dumps())
    cli_out_write("Build profile:")
    cli_out_write(build.dumps())


def profiles_list_cli_output(profiles):
    cli_out_write("Profiles found in the cache:")
    for p in profiles:
        cli_out_write(p)


def detected_profile_cli_output(detect_profile):
    cli_out_write("Detected profile:")
    cli_out_write(detect_profile.dumps())


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


def get_profiles_from_args(args, conan_api):
    # TODO: Do we want a ProfilesAPI.get_profiles() to return both profiles from args?
    profiles = conan_api.profiles
    build = [profiles.get_default_build()] if not args.profile_build else args.profile_build
    host = [profiles.get_default_host()] if not args.profile_host else args.profile_host

    profile_build = profiles.get_profile(profiles=build, settings=args.settings_build,
                                         options=args.options_build, conf=args.conf_build)
    profile_host = profiles.get_profile(profiles=host, settings=args.settings_host,
                                        options=args.options_host, conf=args.conf_host)
    return profile_host, profile_build


@conan_subcommand(formatters={"cli": profiles_cli_output})
def profile_show(conan_api, parser, subparser, *args):
    """
    Show profiles
    """
    add_profiles_args(subparser)
    args = parser.parse_args(*args)
    return get_profiles_from_args(args, conan_api)


@conan_subcommand(formatters={"cli": cli_out_write, "json": json_formatter})
def profile_path(conan_api, parser, subparser, *args):
    """
    Show profile path location
    """
    add_profiles_args(subparser)
    subparser.add_argument("name", help="Profile name")
    args = parser.parse_args(*args)
    result = conan_api.profiles.get_path(args.name)
    return result


@conan_subcommand(formatters={"cli": detected_profile_cli_output})
def profile_detect(conan_api, parser, subparser, *args):
    """
    Detect default profile
    """
    subparser.add_argument("--name", help="Profile name, 'default' if not specified")
    subparser.add_argument("--force", action='store_true', help="Overwrite if exists")
    args = parser.parse_args(*args)

    profile_name = args.name or "default"
    profile_pathname = conan_api.profiles.get_path(profile_name, os.getcwd(), exists=False)
    if not args.force and os.path.exists(profile_pathname):
        raise ConanException(f"Profile '{profile_pathname} already exists")

    detected_profile = conan_api.profiles.detect()
    contents = detected_profile.dumps()
    ConanOutput().info(f"Saving detected profile to {profile_pathname}")
    save(profile_pathname, contents)
    return detected_profile


@conan_subcommand(formatters={"cli": profiles_list_cli_output, "json": json_formatter})
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
