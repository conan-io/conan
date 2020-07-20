import json

from conans.cli.command import conan_command, conan_subcommand, Extender, OnceArgument


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


@conan_subcommand(formatters={"cli": output_user_list_cli, "json": output_user_list_json})
def user_list(*args, conan_api, parser, **kwargs):
    """
    List users and remotes they are associated to.
    """
    parser.add_argument("-r", "--remotes", action=Extender, nargs="?",
                        help="Remotes to show the users from. Multiple remotes can be "
                             "specified: -r remote1 -r remote2. Also wildcards can be "
                             "used. -r '*' will show the users for all the remotes. "
                             "If no remote is specified it will show the users for all "
                             "the remotes")
    args = parser.parse_args(*args)
    if not args.remotes or "*" in args.remotes:
        info = {"results": {"remote1": {"user": "someuser1", "authenticated": True},
                            "remote2": {"user": "someuser2", "authenticated": False},
                            "remote3": {"user": "someuser3", "authenticated": False},
                            "remote4": {"user": "someuser4", "authenticated": True}}}
    else:
        info = {"results": {"remote1": {"user": "someuser1", "authenticated": True}}}
    return info


@conan_subcommand()
def user_add(*args, conan_api, parser, **kwargs):
    """
    Add user authentication for a remote.
    """
    parser.add_argument("name",
                        help="Username")
    parser.add_argument("-p", "--password", action=OnceArgument,
                        help="User password. Use double quotes if password with "
                             "spacing, and escape quotes if existing. If empty, the "
                             "password is requested interactively (not exposed)")
    parser.add_argument("-s", "--skip-auth", action=OnceArgument,
                        help="Skips the authentication with the server if there are "
                             "local stored credentials. It doesn't check if the "
                             "current credentials are valid or not.")
    args = parser.parse_args(*args)
    return {}


@conan_subcommand()
def user_remove(*args, conan_api, parser, **kwargs):
    """
    Remove associated user from remote.
    """
    parser.add_argument("-r", "--remotes", action=Extender, nargs="?", required=True,
                        help="Remotes to remove the users from. Multiple remotes can be "
                             "specified: -r remote1 -r remote2. Also wildcards can be "
                             "used. -r '*' will remove the users for all the remotes.")
    args = parser.parse_args(*args)
    return {}


@conan_subcommand()
def user_update(*args, conan_api, parser, **kwargs):
    """
    Update the current user for a remote.
    """
    parser.add_argument("-r", "--remotes", action=Extender, nargs="?", required=True,
                        help="Remotes to remove the users from. Multiple remotes can "
                             "be specified: -r remote1 -r remote2. Also wildcards can "
                             "be used. -r '*' will remove the users for all the "
                             "remotes.")
    parser.add_argument("-n", "--name", action=OnceArgument,
                        help="Name of the new user. If no name is specified the "
                             "command will update the current user.")
    parser.add_argument("-p", "--password", action=OnceArgument, required=True,
                        const="",
                        type=str,
                        help="Update user password. Use double quotes if password "
                             "with spacing, and escape quotes if existing. If "
                             "empty, the password is requested interactively "
                             "(not exposed)")
    args = parser.parse_args(*args)
    return {}


@conan_command(group="Misc commands")
def user(*args, conan_api, parser, **kwargs):
    """
    Authenticates against a remote with user/pass, caching the auth token.

    Useful to avoid the user and password being requested later. e.g. while
    you're uploading a package.  You can have one user for each remote.
    Changing the user, or introducing the password is only necessary to
    perform changes in remote packages.
    """
    return
