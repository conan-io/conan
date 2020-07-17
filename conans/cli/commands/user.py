import json

from conans.cli.cli import Extender, OnceArgument
from conans.cli.command import conan_command


def output_user_list_json(info, out):
    results = info["results"]
    myjson = json.dumps(results, indent=4)
    out.writeln(myjson)


def output_user_list_cli(info, out):
    results = info["results"]
    for remote, user_info in results.items():
        output_str = "user: {} authenticated: {}".format(user_info["user"],
                                                         user_info["authenticated"])
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
                                    help="Remotes to show the users from. Multiple remotes can be "
                                         "specified: -r remote1 -r remote2. Also wildcards can be "
                                         "used. -r '*' will show the users for all the remotes. "
                                         "If no remote is specified it will show the users for all "
                                         "the remotes")

    # add subcommand
    subparsers["add"].add_argument("name",
                                   help="Username you want to use.")
    subparsers["add"].add_argument("-p", "--password", action=OnceArgument,
                                   help="User password. Use double quotes if password with "
                                        "spacing, and escape quotes if existing. If empty, the "
                                        "password is requested interactively (not exposed)")
    subparsers["add"].add_argument("-s", "--skip-auth", action=OnceArgument,
                                   help="Skips the authentication with the server if there are "
                                        "local stored credentials. It doesn't check if the "
                                        "current credentials are valid or not.")

    # remove subcommand
    subparsers["remove"].add_argument("-r", "--remotes", action=Extender, nargs="?", required=True,
                                      help="Remotes to remove the users from. Multiple remotes can be "
                                           "specified: -r remote1 -r remote2. Also wildcards can be "
                                           "used. -r '*' will remove the users for all the remotes.")

    # update subcommand
    subparsers["update"].add_argument("-r", "--remotes", action=Extender, nargs="?", required=True,
                                      help="Remotes to remove the users from. Multiple remotes can "
                                           "be specified: -r remote1 -r remote2. Also wildcards can "
                                           "be used. -r '*' will remove the users for all the "
                                           "remotes.")
    subparsers["update"].add_argument("-n", "--name", action=OnceArgument,
                                      help="Name of the new user. If no name is specified the "
                                           "command will update the current user.")
    subparsers["update"].add_argument("-p", "--password", action=OnceArgument, required=True,
                                      const="",
                                      type=str,
                                      help="Update user password. Use double quotes if password "
                                           "with spacing, and escape quotes if existing. If "
                                           "empty, the password is requested interactively "
                                           "(not exposed)")

    args = parser.parse_args(*args)
    info = {}
    if args.subcommand == "list":
        if "*" in args.remotes:
            info = {"results": {"remote1": {"user": "someuser1", "authenticated": True},
                                "remote2": {"user": "someuser2", "authenticated": False},
                                "remote3": {"user": "someuser3", "authenticated": False},
                                "remote4": {"user": "someuser4", "authenticated": True}}}
        else:
            info = {"results": {"remote1": {"user": "someuser1", "authenticated": True}}}

    return info
