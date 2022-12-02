import os

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands import default_text_formatter, default_json_formatter
from conan.cli.args import add_profiles_args
from conans.errors import ConanException
from conans.util.files import save


def print_profiles(profiles):
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


@conan_subcommand(formatters={"text": print_profiles})
def profile_show(conan_api, parser, subparser, *args):
    """
    Show profiles
    """
    add_profiles_args(subparser)
    args = parser.parse_args(*args)
    result = conan_api.profiles.get_profiles_from_args(args)
    return result


@conan_subcommand(formatters={"text": default_text_formatter})
def profile_path(conan_api, parser, subparser, *args):
    """
    Show profile path location
    """
    add_profiles_args(subparser)
    subparser.add_argument("name", help="Profile name")
    args = parser.parse_args(*args)
    return conan_api.profiles.get_path(args.name)


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


@conan_subcommand(formatters={"text": profiles_list_cli_output, "json": default_json_formatter})
def profile_list(conan_api, parser, subparser, *args):
    """
    List all profiles in the cache
    """
    result = conan_api.profiles.list()
    return result


@conan_command(group="Consumer")
def profile(conan_api, parser, *args):
    """
    Manages profiles
    """
