import json

from conans.cli.cli import cli_out_write
from conans.cli.command import conan_command, conan_subcommand, Extender, OnceArgument


def output_user_list_json(info):
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


def output_user_list_cli(info):
    for remote_name, user_info in info.items():
        output_str = "remote: {} user: {}".format(remote_name,
                                                  user_info["user"])
        cli_out_write(output_str)


@conan_subcommand(formatters={"cli": output_user_list_cli, "json": output_user_list_json})
def user_list(conan_api, parser, subparser, *args):
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
    info = conan_api.user_list(args.remote)
    return info


# no user associated with remote yet
@conan_subcommand()
def user_add(conan_api, parser, subparser, *args):
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


@conan_subcommand()
def user_remove(conan_api, parser, subparser, *args):
    """
    Remove associated user from remote.
    """
    subparser.add_argument("remote",
                           help="Remote name. Accepts 'fnmatch' style wildcards. "
                                "To remove the user for all remotes use: conan remote remove \"*\"")
    args = parser.parse_args(*args)


@conan_subcommand()
def user_update(conan_api, parser, subparser, *args):
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


@conan_command(group="Misc")
def user(conan_api, parser, *args, **kwargs):
    """
    Authenticates against a remote with user/pass, caching the auth token.

    Useful to avoid the user and password being requested later. e.g. while
    you're uploading a package.  You can have one user for each remote.
    Changing the user, or introducing the password is only necessary to
    perform changes in remote packages.
    """
