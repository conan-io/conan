import json
import os

from conan.api.output import ConanOutput, cli_out_write
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.formatters import default_json_formatter
from conan.cli.args import add_profiles_args
from conan.errors import ConanException
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


def json_profiles(profiles):
    host, build = profiles
    result = {"host": host.serialize(),
              "build": build.serialize()}
    cli_out_write(json.dumps(result))


@conan_subcommand(formatters={"text": print_profiles, "json": json_profiles})
def profile_show(conan_api, parser, subparser, *args):
    """
    Show aggregated profiles from the passed arguments.
    """
    add_profiles_args(subparser)
    args = parser.parse_args(*args)
    result = conan_api.profiles.get_profiles_from_args(args)
    return result


@conan_subcommand(formatters={"text": cli_out_write})
def profile_path(conan_api, parser, subparser, *args):
    """
    Show profile path location.
    """
    subparser.add_argument("name", help="Profile name")
    args = parser.parse_args(*args)
    return conan_api.profiles.get_path(args.name)


@conan_subcommand()
def profile_detect(conan_api, parser, subparser, *args):
    """
    Generate a profile using auto-detected values.
    """
    subparser.add_argument("--name", help="Profile name, 'default' if not specified")
    subparser.add_argument("-f", "--force", action='store_true', help="Overwrite if exists")
    subparser.add_argument("-e", "--exist-ok", action='store_true',
                           help="If the profile already exist, do not detect a new one")
    args = parser.parse_args(*args)

    profile_name = args.name or "default"
    profile_pathname = conan_api.profiles.get_path(profile_name, os.getcwd(), exists=False)
    if os.path.exists(profile_pathname):
        if args.exist_ok:
            ConanOutput().info(f"Profile '{profile_name}' already exists, skipping detection")
            return
        if not args.force:
            raise ConanException(f"Profile '{profile_pathname}' already exists")

    detected_profile = conan_api.profiles.detect()
    ConanOutput().success("\nDetected profile:")
    cli_out_write(detected_profile.dumps())

    contents = detected_profile.dumps()
    ConanOutput().warning("This profile is a guess of your environment, please check it.")
    if detected_profile.settings.get("os") == "Macos":
        ConanOutput().warning("Defaulted to cppstd='gnu17' for apple-clang.")
    ConanOutput().warning("The output of this command is not guaranteed to be stable and can "
                          "change in future Conan versions.")
    ConanOutput().warning("Use your own profile files for stability.")
    ConanOutput().success(f"Saving detected profile to {profile_pathname}")
    save(profile_pathname, contents)


@conan_subcommand(formatters={"text": profiles_list_cli_output, "json": default_json_formatter})
def profile_list(conan_api, parser, subparser, *args):
    """
    List all profiles in the cache.
    """
    result = conan_api.profiles.list()
    return result


@conan_command(group="Consumer")
def profile(conan_api, parser, *args):
    """
    Manage profiles.
    """
