import os

from conans.cli.command import conan_command, conan_subcommand, COMMAND_GROUPS
from conans.cli.commands import json_formatter
from conans.cli.common import add_profiles_args, get_profiles_from_args
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


@conan_subcommand(formatters={"cli": profiles_cli_output})
def profile_show(conan_api, parser, subparser, *args):
    """
    Show profiles
    """
    add_profiles_args(subparser)
    args = parser.parse_args(*args)
    return get_profiles_from_args(conan_api, args)


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
def profile(conan_api, parser, *args):
    """
    Manages profiles
    """
