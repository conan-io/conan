import json

from conans.client.output import Color
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.cli.command import OnceArgument, Extender, conan_command


#  This command accepts a conan package reference as input. Could be in different forms:
#  name/version
#  name/version@user/channel
#  name/version@user/channel#<recipe_revision>
#  name/version@user/channel#<recipe_revision>:<package_id>
#  name/version@user/channel#<recipe_revision>:<package_id>#<package_revision>

def output_dig_cli(info, out):
    results = info["results"]
    for remote_info in results:
        source = "cache" if remote_info["remote"] is None else str(remote_info["remote"])
        out.writeln("{}:".format(source), Color.BRIGHT_WHITE)
        for conan_item in remote_info["items"]:
            reference = conan_item["recipe"]["id"]
            out.writeln(" {}".format(reference), Color.BRIGHT_GREEN)
            for package in conan_item["packages"]:
                out.writeln(" :{}".format(package["id"]), Color.BRIGHT_GREEN)
                out.writeln("  [options]", Color.BRIGHT_WHITE)
                for option, value in package["options"].items():
                    out.write("  {}: ".format(option), Color.YELLOW)
                    out.write("{}".format(value), newline=True)
                out.writeln("  [settings]", Color.BRIGHT_WHITE)
                for setting, value in package["settings"].items():
                    out.write("  {}: ".format(setting), Color.YELLOW)
                    out.write("{}".format(value), newline=True)


def output_dig_json(info, out):
    myjson = json.dumps(info["results"], indent=4)
    out.writeln(myjson)


@conan_command(group="Consumer commands", cli=output_dig_cli, json=output_dig_json)
def dig(*args, conan_api, parser, **kwargs):
    """
    Gets information about available package binaries in the local cache or a remote
    """

    parser.add_argument('reference',
                        help="Package recipe reference, e.g., 'zlib/1.2.8', \
                             'boost/1.73.0@mycompany/stable'")

    exclusive_args = parser.add_mutually_exclusive_group()
    exclusive_args.add_argument('-r', '--remote', default=None, action=Extender, nargs='?',
                                help="Remote to search. Accepts wildcards. To search in all remotes use *")
    exclusive_args.add_argument('-c', '--cache', action="store_true",
                                help="Search in the local cache")
    parser.add_argument('-o', '--output', default="cli", action=OnceArgument,
                        help="Select the output format: json, html,...")
    args = parser.parse_args(*args)

    try:
        remotes = args.remote if args.remote is not None else []
        ref = ConanFileReference.loads(args.reference)
        info = conan_api.search_packages(ref, query=None,
                                         remote_patterns=remotes,
                                         outdated=False,
                                         local_cache=args.cache)
    except ConanException as exc:
        info = exc.info
        raise
    finally:
        return info, args.output
