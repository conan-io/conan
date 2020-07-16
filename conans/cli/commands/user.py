import json

from conans.client.output import Color
from conans.cli.cli import Extender
from conans.cli.command import conan_command


def output_user_list_json(info, out):
    results = info["results"]
    myjson = json.dumps(results, indent=4)
    out.writeln(myjson)


def output_user_list_cli(info, out):
    results = info["results"]
    output_str = "user: {} authenticated: {}".format(results["user"], results["authenticated"])
    out.writeln(output_str)


list_formatters = {"cli": output_user_list_cli,
                   "json": output_user_list_json}

subcommands = [{"name": "list", "help": "List users and remotes they are associated to"},
               {"name": "add", "help": "Add user authentication for a remote"},
               {"name": "remove", "help": "Remove associated user from remote"},
               {"name": "update", "help": "Update the current user for a remote"}]

formatters = {"list": list_formatters}


@conan_command(group="Misc commands", formatters=formatters, subcommands=subcommands)
def user(*args, conan_api, parser, subparsers, **kwargs):
    # list, add, remove, update
    """
    Authenticates against a remote with user/pass, caching the auth token.

    Useful to avoid the user and password being requested later. e.g. while
    you're uploading a package.  You can have one user for each remote.
    Changing the user, or introducing the password is only necessary to
    perform changes in remote packages.
    """
    # list subcommand
    subparsers["list"].add_argument("-r", "--remotes", action=Extender, nargs="?",
                                    help="Show the user for the selected remote")

    # add subcommand
    subparsers["add"].add_argument("name",
                                   help="Username you want to use. If no name is provided it")
    subparsers["add"].add_argument("-p", "--password", action=Extender, nargs="?",
                                   help="User password. Use double quotes if password with "
                                        "spacing, and escape quotes if existing. If empty, the "
                                        "password is requested interactively (not exposed)")
    args = parser.parse_args(*args)
    info = {}
    if args.subcommand == "list":
        info = {"results": {"user": "someuser", "authenticated": True}}

    return info
