import json

from conans.cli.cli import cli_out_write
from conans.cli.command import conan_command, conan_subcommand, OnceArgument


def output_remote_list_json(info):
    myjson = json.dumps(info, indent=4)
    cli_out_write(myjson)


def output_remote_list_cli(info):
    for remote_info in info:
        output_str = "{}: {} [SSL: {}, Enabled: {}]".format(remote_info["name"],
                                                            remote_info["url"],
                                                            remote_info["ssl"],
                                                            remote_info["enabled"])
        cli_out_write(output_str)


@conan_subcommand(formatters={"cli": output_remote_list_cli, "json": output_remote_list_json})
def remote_list(conan_api, parser, subparser, *args):
    """
    List current remotes
    """
    args = parser.parse_args(*args)
    info = [{"name": "remote1", "url": "https://someurl1", "ssl": True, "enabled": False},
            {"name": "remote2", "url": "https://someurl2", "ssl": False, "enabled": True},
            {"name": "remote3", "url": "https://someurl3", "ssl": True, "enabled": True},
            {"name": "remote4", "url": "https://someurl4", "ssl": False, "enabled": False}]
    return info


@conan_subcommand()
def remote_add(conan_api, parser, subparser, *args):
    """
    Add a remote
    """
    subparser.add_argument("remote", help="Name of the remote to add")
    subparser.add_argument("url", help="Url for the rempote")
    subparser.add_argument("--no-ssl", dest="no_ssl", action="store_true", default=False)
    subparser.add_argument("--insert", action=OnceArgument, type=int,
                           help="Insert remote at specific index")
    subparser.add_argument("--force", action='store_true', default=False,
                           help="Force addition, will update if existing")
    args = parser.parse_args(*args)


@conan_subcommand()
def remote_remove(conan_api, parser, subparser, *args):
    """
    Remove conan remotes
    """
    subparser.add_argument("remote", help="Name of the remote to remove. "
                                          "Accepts 'fnmatch' style wildcards.")  # to discuss
    args = parser.parse_args(*args)


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
    subparser.add_argument("--insert", action=OnceArgument, type=int,
                           help="Insert remote at specific index")
    args = parser.parse_args(*args)
    if not (args.name or args.url or args.no_ssl or args.insert):
        subparser.error("Please add at least one remote field to update: "
                        "name, url, disable-ssl, insert")


@conan_subcommand()
def remote_enable(conan_api, parser, subparser, *args):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to enable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)


@conan_subcommand()
def remote_disable(conan_api, parser, subparser, *args):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to disable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)


@conan_command(group="Misc commands")
def remote(conan_api, parser, *args, **kwargs):
    """
    Manages the remote list and the package recipes associated with a remote.
    """
