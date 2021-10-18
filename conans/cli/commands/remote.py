import json

from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.api.model import Remote
from conans.cli.command import conan_command, conan_subcommand, OnceArgument
from conans.cli.output import cli_out_write
from conans.errors import ConanException


@conan_command()
def remote(conan_api, parser, *args, **kwargs):
    """
    Manages the remote list and the users authenticated on them.
    """


def output_remote_list_json(remotes):
    info = [{"name": r.name, "url": r.url, "verify_ssl": r.verify_ssl, "enabled": not r.disabled}
            for r in remotes]
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


def output_remote_list_cli(remote):
    for remote in remote:
        output_str = str(remote)
        cli_out_write(output_str)


@conan_subcommand(formatters={"cli": output_remote_list_cli, "json": output_remote_list_json})
def remote_list(conan_api: ConanAPIV2, parser, subparser, *args):
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
    current = conan_api.remotes.get(args.remote)
    conan_api.remotes.remove(current)


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
    remotes = conan_api.remotes.list(filter=args.remote)
    for r in remotes:
        r.disabled = False
        conan_api.remotes.update(r)


@conan_subcommand()
def remote_disable(conan_api, parser, subparser, *args):
    """
    Disable all the remotes matching a pattern
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to disable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(filter=args.remote)
    for r in remotes:
        r.disabled = True
        conan_api.remotes.update(r)

