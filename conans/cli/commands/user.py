import json

from conans.cli.command import conan_command, conan_subcommand, Extender, OnceArgument


def output_user_list_json(info, out):
    results = info["results"]
    myjson = json.dumps(results, indent=4)
    out.writeln(myjson)


def output_user_list_cli(info, out):
    results = info["results"]
    for remote_name, user_info in results.items():
        output_str = "remote: {} user: {}".format(remote_name,
                                                  user_info["user"])
        out.writeln(output_str)


@conan_subcommand(formatters={"cli": output_user_list_cli, "json": output_user_list_json})
def user_list(*args, conan_api, parser, subparser):
    """
    List users and remotes they are associated to.
    """
    subparser.add_argument("-r", "--remote", action=Extender, nargs="?",
                           help="Remotes to show the users from. Multiple remotes can be "
                                "specified: -r remote1 -r remote2. Also wildcards can be "
                                "used. -r \"*\" will show the users for all the remotes. "
                                "If no remote is specified it will show the users for all "
                                "the remotes")
    args = parser.parse_args(*args)
    if not args.remote or "*" in args.remote:
        info = {"results": {"remote1": {"user": "someuser1"},
                            "remote2": {"user": "someuser2"},
                            "remote3": {"user": "someuser3"},
                            "remote4": {"user": "someuser4"}}}
    else:
        info = {"results": {"remote1": {"user": "someuser1"}}}
    return info


# no user associated with remote yet
@conan_subcommand()
def user_add(*args, conan_api, parser, subparser):
    """
    Add user authentication for a remote.
    """
    subparser.add_argument("remote", help="Remote name")
    # conan user add command should ask for the name and password in case none of them are
    # passed as arguments. If just --name, ask for password. If --password is passed ask for
    # username
    subparser.add_argument("-n", "--name", action=OnceArgument,
                           help="User password. Use double quotes if password with "
                                "spacing, and escape quotes if existing. If empty, the "
                                "password is requested interactively (not exposed)")
    subparser.add_argument("-p", "--password", action=OnceArgument, nargs="?",
                           help="User password. Use double quotes if password with "
                                "spacing, and escape quotes if existing. If empty, the "
                                "password is requested interactively (not exposed)")
    subparser.add_argument("-f", "--force", action='store_true', default=False,
                           help="Force addition, will update if existing.")
    args = parser.parse_args(*args)
    return {}


@conan_subcommand()
def user_remove(*args, conan_api, parser, subparser):
    """
    Remove associated user from remote.
    """
    subparser.add_argument("remote",
                           help="Remote name. Accepts 'fnmatch' style wildcards. "
                                "To remove the user for all remotes use: conan remote remove \"*\"")
    args = parser.parse_args(*args)
    return {}


@conan_subcommand()
def user_update(*args, conan_api, parser, subparser):
    """
    Update the current user for a remote. If not 'user' and 'password' are passed it will ask
    for them interactively.
    """
    subparser.add_argument("remote", help="Remote name")
    # changing the name of the user forces a password change, it will be requested interactively
    # if not passed as an argument

    subparser.add_argument("-n", "--name", action=OnceArgument,
                           help="Name of the new user. If no name is specified the "
                                "command will update the current user.")
    subparser.add_argument("-p", "--password", nargs="?", action=OnceArgument,
                           help="Update user password. Use double quotes if password "
                                "with spacing, and escape quotes if existing. If "
                                "empty, the password is requested interactively "
                                "(not exposed)")
    args = parser.parse_args(*args)
    return {}


@conan_command(group="Misc")
def user(*args, conan_api, parser, **kwargs):
    """
    Authenticates against a remote with user/pass, caching the auth token.

    Useful to avoid the user and password being requested later. e.g. while
    you're uploading a package.  You can have one user for each remote.
    Changing the user, or introducing the password is only necessary to
    perform changes in remote packages.
    """
    return
