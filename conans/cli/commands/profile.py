import os

from conans.cli.command import conan_command, conan_subcommand, COMMAND_GROUPS
from conans.cli.commands import json_formatter
from conans.cli.common import add_profiles_args, get_profiles_from_args
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.util.files import save


def print_profiles(profiles):
    host, build = profiles
    out = ConanOutput()
    out.writeln("Host profile:")
    out.writeln(host.dumps())
    out.writeln("Build profile:")
    out.writeln(build.dumps())


def profiles_list_cli_output(profiles):
    out = ConanOutput()
    out.writeln("Profiles found in the cache:")
    for p in profiles:
        out.writeln(p)


def detected_profile_cli_output(detect_profile):
    out = ConanOutput()
    out.writeln("Detected profile:")
    out.writeln(detect_profile.dumps())


@conan_subcommand()
def profile_show(conan_api, parser, subparser, *args):
    """
    Show profiles
    """
    add_profiles_args(subparser)
    args = parser.parse_args(*args)
    result = get_profiles_from_args(conan_api, args)
    print_profiles(result)
    return result


@conan_subcommand(formatters={"text": lambda x: x, "json": json_formatter})
def profile_path(conan_api, parser, subparser, *args):
    """
    Show profile path location
    """
    add_profiles_args(subparser)
    subparser.add_argument("name", help="Profile name")
    args = parser.parse_args(*args)
    result = conan_api.profiles.get_path(args.name)
    out = ConanOutput()
    out.writeln(result)
    return result


@conan_subcommand()
def profile_detect(conan_api, parser, subparser, *args):
    """
    Detect default profile
    """
    subparser.add_argument("--name", help="Profile name, 'default' if not specified")
    subparser.add_argument("-f", "--force", action='store_true', help="Overwrite if exists")
    args = parser.parse_args(*args)

    profile_name = args.name or "default"
    profile_pathname = conan_api.profiles.get_path(profile_name, os.getcwd(), exists=False)
    if not args.force and os.path.exists(profile_pathname):
        raise ConanException(f"Profile '{profile_pathname}' already exists")

    detected_profile = conan_api.profiles.detect()
    detected_profile_cli_output(detected_profile)
    contents = detected_profile.dumps()
    ConanOutput().warning("This profile is a guess of your environment, please check it.")
    ConanOutput().warning("The output of this command is not guaranteed to be stable and can "
                          "change in future Conan versions")
    ConanOutput().success(f"Saving detected profile to {profile_pathname}")
    save(profile_pathname, contents)


@conan_subcommand(formatters={"json": json_formatter})
def profile_list(conan_api, parser, subparser, *args):
    """
    List all profiles in the cache
    """
    result = conan_api.profiles.list()
    profiles_list_cli_output(result)
    return result


@conan_command(group=COMMAND_GROUPS['consumer'])
def profile(conan_api, parser, *args):
    """
    Manages profiles
    """
