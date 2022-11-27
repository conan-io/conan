import json
from collections import OrderedDict

from conan.api.output import cli_out_write
from conan.api.conan_api import ConanAPI
from conan.api.model import Remote
from conan.cli.command import conan_command, conan_subcommand, OnceArgument
from conan.cli.commands.list import remote_color, error_color, recipe_color, \
    reference_color
from conans.client.userio import UserInput
from conans.errors import ConanException


def formatter_remote_list_json(remotes):
    info = [{"name": r.name, "url": r.url, "verify_ssl": r.verify_ssl, "enabled": not r.disabled}
            for r in remotes]
    cli_out_write(json.dumps(info, indent=4))


def print_remote_list(remotes):
    for r in remotes:
        output_str = str(r)
        cli_out_write(output_str)


def print_remote_user_list(results):
    for remote_name, result in results.items():
        cli_out_write(f"{remote_name}:", fg=remote_color)
        if result["user_name"] is None:
            cli_out_write("  No user", fg=error_color)
        else:
            cli_out_write("  Username: ", fg=recipe_color, endline="")
            cli_out_write(result["user_name"], fg=reference_color)
            cli_out_write("  authenticated: ", fg=recipe_color, endline="")
            cli_out_write(result["authenticated"], fg=reference_color)


def print_remote_user_set(results):
    for remote_name, result in results.items():
        from_user = "'{}'".format(result["previous_info"]["user_name"])
        from_user += " (anonymous)" \
            if not result["previous_info"]["authenticated"] else " (authenticated)"
        to_user = "'{}'".format(result["info"]["user_name"])
        to_user += " (anonymous)" \
            if not result["info"]["authenticated"] else " (authenticated)"
        message = "Changed user of remote '{}' from {} to {}".format(remote_name, from_user, to_user)
        cli_out_write(message)


def output_remotes_json(results):
    cli_out_write(json.dumps(list(results.values())))


@conan_subcommand(formatters={"text": print_remote_list, "json": formatter_remote_list_json})
def remote_list(conan_api: ConanAPI, parser, subparser, *args):
    """
    List current remotes
    """
    return conan_api.remotes.list()


@conan_subcommand()
def remote_add(conan_api, parser, subparser, *args):
    """
    Add a remote
    """
    subparser.add_argument("name", help="Name of the remote to add")
    subparser.add_argument("url", help="Url of the remote")
    subparser.add_argument("--secure", dest="secure", action='store_true',
                           help="Don't allow insecure server connections when using SSL")
    subparser.add_argument("--insecure", dest="secure", action='store_false',
                           help="Allow insecure server connections when using SSL")
    subparser.add_argument("--index", action=OnceArgument, type=int,
                           help="Insert the remote at a specific position in the remote list")
    subparser.set_defaults(secure=True)
    args = parser.parse_args(*args)
    index = _check_index_argument(args.index)
    r = Remote(args.name, args.url, args.secure, disabled=False)
    conan_api.remotes.add(r)
    if index is not None:
        conan_api.remotes.move(r, index)


def _check_index_argument(index):
    if index is None:
        return None
    try:
        return int(index)
    except ValueError:
        raise ConanException("index argument must be an integer")


@conan_subcommand()
def remote_remove(conan_api, parser, subparser, *args):
    """
    Remove a remote
    """
    subparser.add_argument("remote", help="Name of the remote to remove. "
                                          "Accepts 'fnmatch' style wildcards.")  # to discuss
    args = parser.parse_args(*args)
    conan_api.remotes.remove(args.remote)


@conan_subcommand()
def remote_update(conan_api, parser, subparser, *args):
    """
    Update the remote
    """
    subparser.add_argument("remote", help="Name of the remote to update")
    subparser.add_argument("--url", action=OnceArgument, help="New url for the remote")
    subparser.add_argument("--secure", dest="secure", action='store_true',
                           help="Don't allow insecure server connections when using SSL")
    subparser.add_argument("--insecure", dest="secure", action='store_false',
                           help="Allow insecure server connections when using SSL")
    subparser.add_argument("--index", action=OnceArgument, type=int,
                           help="Insert the remote at a specific position in the remote list")
    subparser.set_defaults(secure=None)
    args = parser.parse_args(*args)
    if not (args.url is not None or args.secure is not None):
        subparser.error("Please add at least one argument to update")
    r = conan_api.remotes.get(args.remote)
    if args.url is not None:
        r.url = args.url
    if args.secure is not None:
        r.verify_ssl = args.secure
    conan_api.remotes.update(r)


@conan_subcommand()
def remote_rename(conan_api, parser, subparser, *args):
    """
    Rename a remote
    """
    subparser.add_argument("remote", help="Current name of the remote")
    subparser.add_argument("new_name", help="New name for the remote")
    args = parser.parse_args(*args)
    r = conan_api.remotes.get(args.remote)
    conan_api.remotes.rename(r, args.new_name)


@conan_subcommand()
def remote_move(conan_api, parser, subparser, *args):
    """
    Move the position of the remote in the remotes list (first in the list: first called)
    """
    subparser.add_argument("remote", help="Name of the remote to update")
    subparser.add_argument("index", action=OnceArgument, type=int,
                           help="Insert remote at specific index")
    args = parser.parse_args(*args)
    r = conan_api.remotes.get(args.remote)
    index = _check_index_argument(args.index)
    conan_api.remotes.move(r, index)


@conan_subcommand()
def remote_enable(conan_api, parser, subparser, *args):
    """
    Enable all the remotes matching a pattern
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to enable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)
    conan_api.remotes.enable(args.remote)


@conan_subcommand()
def remote_disable(conan_api, parser, subparser, *args):
    """
    Disable all the remotes matching a pattern
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to disable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)
    conan_api.remotes.disable(args.remote)


# ### User related commands

@conan_subcommand(formatters={"text": print_remote_user_list, "json": output_remotes_json})
def remote_list_users(conan_api, parser, subparser, *args):
    """List the users logged into the remotes"""
    remotes = conan_api.remotes.list()
    ret = OrderedDict()
    if not remotes:
        raise ConanException("No remotes defined")
    for r in remotes:
        ret[r.name] = conan_api.remotes.user_info(r)

    return ret


@conan_subcommand(formatters={"text": print_remote_user_set, "json": output_remotes_json})
def remote_login(conan_api, parser, subparser, *args):
    """Login into the specified remotes"""
    subparser.add_argument("remote", help="Pattern or name of the remote to login into. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    subparser.add_argument("username", help='Username')
    subparser.add_argument("-p", "--password", nargs='?', const="", type=str, action=OnceArgument,
                           help='User password. Use double quotes if password with spacing, '
                                'and escape quotes if existing. If empty, the password is '
                                'requested interactively (not exposed)')

    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(pattern=args.remote)
    if not remotes:
        raise ConanException("There are no remotes matching the '{}' pattern".format(args.remote))

    password = args.password
    if not password:
        ui = UserInput(conan_api.config.get("core:non_interactive"))
        _, password = ui.request_login(remote_name=args.remote, username=args.username)

    ret = OrderedDict()
    for r in remotes:
        previous_info = conan_api.remotes.user_info(r)
        conan_api.remotes.login(r, args.username, password)
        info = conan_api.remotes.user_info(r)
        ret[r.name] = {"previous_info": previous_info, "info": info}

    return ret


@conan_subcommand(formatters={"text": print_remote_user_set, "json": output_remotes_json})
def remote_set_user(conan_api, parser, subparser, *args):
    """Associates a username with a remote without performing the authentication"""
    subparser.add_argument("remote", help="Pattern or name of the remote. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    subparser.add_argument("username", help='Username')

    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(pattern=args.remote)
    if not remotes:
        raise ConanException("There are no remotes matching the '{}' pattern".format(args.remote))

    ret = OrderedDict()
    for r in remotes:
        previous_info = conan_api.remotes.user_info(r)
        if previous_info["user_name"] != args.username:
            conan_api.remotes.logout(r)
            conan_api.remotes.user_set(r, args.username)
        ret[r.name] = {"previous_info": previous_info, "info": conan_api.remotes.user_info(r)}
    return ret


@conan_subcommand(formatters={"text": print_remote_user_set, "json": output_remotes_json})
def remote_logout(conan_api, parser, subparser, *args):
    """Clear the existing credentials for the specified remotes"""
    subparser.add_argument("remote", help="Pattern or name of the remote to logout. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(pattern=args.remote)
    if not remotes:
        raise ConanException("There are no remotes matching the '{}' pattern".format(args.remote))

    ret = OrderedDict()
    for r in remotes:
        previous_info = conan_api.remotes.user_info(r)
        conan_api.remotes.logout(r)
        info = conan_api.remotes.user_info(r)
        ret[r.name] = {"previous_info": previous_info, "info": info}
    return ret


@conan_command(group="Consumer")
def remote(conan_api, parser, *args):
    """
    Manages the remote list and the users authenticated on them.
    """
