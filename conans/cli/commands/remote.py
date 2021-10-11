import json

from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.api.model import Remote
from conans.cli.command import conan_command, conan_subcommand, OnceArgument
from conans.cli.output import cli_out_write
from conans.errors import ConanException


@conan_command()
def remote(conan_api, parser, *args, **kwargs):
    """
    Manages the remote list and the package recipes associated with a remote.
    """


def output_remote_list_json(remotes):
    info = [{"name": r.name, "url": r.url, "ssl": r.verify_ssl, "enabled": not r.disabled}
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
    subparser.add_argument("--no-ssl", dest="no_ssl", action="store_true", default=False)
    subparser.add_argument("--index", action=OnceArgument, type=int,
                           help="Insert remote at specific position in the remote list")
    args = parser.parse_args(*args)
    index = _check_index_argument(args.index)
    verify_ssl = not args.no_ssl
    remote = Remote(args.name, args.url, verify_ssl, disabled=False)
    conan_api.remotes.add(remote)
    if index is not None:
        conan_api.remotes.move(remote, index)


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
    Remove conan remotes
    """
    subparser.add_argument("remote", help="Name of the remote to remove. "
                                          "Accepts 'fnmatch' style wildcards.")  # to discuss
    args = parser.parse_args(*args)
    current = conan_api.remotes.get(args.remote)
    conan_api.remotes.remove(current)


@conan_subcommand()
def remote_update(conan_api, parser, subparser, *args):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Name of the remote to update")
    subparser.add_argument("--name", action=OnceArgument,
                           help="New name for the remote")
    subparser.add_argument("--url", action=OnceArgument,
                           help="New url for the remote")
    subparser.add_argument("--no-ssl", dest="no_ssl", action=OnceArgument, type=bool,
                           choices=[True, False])
    args = parser.parse_args(*args)
    if not (args.name or args.url or args.no_ssl):
        subparser.error("Please add at least one remote field to update: "
                        "name, url, disable-ssl")
    remote = conan_api.remotes.get(args.remote)
    if args.name:
        conan_api.remotes.rename(remote, args.name)
    if args.url:
        remote.url = args.url
    if args.no_ssl:
        remote.verify_ssl = not args.no_ssl

    conan_api.remotes.update(remote)


@conan_subcommand()
def remote_move(conan_api, parser, subparser, *args):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Name of the remote to update")
    subparser.add_argument("index", action=OnceArgument, type=int,
                           help="Insert remote at specific index")
    args = parser.parse_args(*args)
    remote = conan_api.remotes.get(args.remote)
    index = _check_index_argument(args.index)
    conan_api.remotes.move(remote, index)


@conan_subcommand()
def remote_enable(conan_api, parser, subparser, *args):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to enable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(filter=args.remote)
    for remote in remotes:
        remote.disabled = False
        conan_api.remotes.update(remote)


@conan_subcommand()
def remote_disable(conan_api, parser, subparser, *args):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to disable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(filter=args.remote)
    for remote in remotes:
        remote.disabled = True
        conan_api.remotes.update(remote)

