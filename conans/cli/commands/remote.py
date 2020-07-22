import json

from conans.cli.command import conan_command, conan_subcommand, Extender, OnceArgument


def output_remote_list_json(info, out):
    results = info["results"]
    myjson = json.dumps(results, indent=4)
    out.writeln(myjson)


def output_remote_list_cli(info, out):
    results = info["results"]
    for remote_name, remote_info in results.items():
        output_str = "{}: {} [Verify SSL: {}, Enabled: {}]".format(remote_name,
                                                                   remote_info["url"],
                                                                   remote_info["verify"],
                                                                   remote_info.get(
                                                                       "disabled", False))
        out.writeln(output_str)


@conan_subcommand(formatters={"cli": output_remote_list_cli, "json": output_remote_list_json})
def remote_list(*args, conan_api, parser, subparser):
    """
    List current remotes
    """
    args = parser.parse_args(*args)
    info = {"results": {"remote1": {"url": "https://someurl1", "verify": True},
                        "remote2": {"url": "https://someurl2", "verify": False,
                                    "disabled": True},
                        "remote3": {"url": "https://someurl3", "verify": False},
                        "remote4": {"url": "https://someurl4", "verify": True}}}
    return info


@conan_subcommand()
def remote_add(*args, conan_api, parser, subparser):
    """
    Add a remote
    """
    subparser.add_argument("remote", help="Name of the remote to add")
    subparser.add_argument("-u", "--url", action=OnceArgument, required=True,
                           help="New url for the rempote")
    subparser.add_argument("-v", "--verify_ssl", action=OnceArgument, default="True",
                           help="Verify SSL certificated")
    subparser.add_argument("-i", "--insert", action=OnceArgument,
                           help="Insert remote at specific index")
    subparser.add_argument("-f", "--force", action='store_true', default=False,
                           help="Force addition, will update if existing")
    args = parser.parse_args(*args)
    return {}


@conan_subcommand()
def remote_remove(*args, conan_api, parser, subparser):
    """
    Remove conan remotes
    """
    subparser.add_argument("remote", help="Name of the remote to remove. "
                                          "Accepts 'fnmatch' style wildcards.")  # to discuss
    args = parser.parse_args(*args)
    return {}


@conan_subcommand()
def remote_update(*args, conan_api, parser, subparser):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Name of the remote to update")
    subparser.add_argument("-n", "--name", action=OnceArgument,
                           help="New name for the remote")
    subparser.add_argument("-u", "--url", action=OnceArgument,
                           help="New url for the rempote")
    subparser.add_argument("-v", "--verify_ssl", action=OnceArgument,
                           help="Verify SSL certificated")
    subparser.add_argument("-i", "--insert", action=OnceArgument,
                           help="Insert remote at specific index")
    args = parser.parse_args(*args)
    if not (args.name or args.url or args.verify_ssl or args.insert):
        subparser.error("Please add at least one remote field to update: """
                        "name, url, verify_ssl, insert")
    return {}


# to discuss: conan remote update --enable 1
@conan_subcommand()
def remote_enable(*args, conan_api, parser, subparser):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Name of the remote to enable")
    args = parser.parse_args(*args)
    return {}


# to discuss: conan remote update --enable 0
@conan_subcommand()
def remote_disable(*args, conan_api, parser, subparser):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Name of the remote to disable")
    args = parser.parse_args(*args)
    return {}


# to discuss: conan remote update --enable 0
@conan_subcommand()
def remote_references(*args, conan_api, parser, subparser):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Name of the remote to disable")
    args = parser.parse_args(*args)
    return {}


# remote references management --> move to new command?
# list_ref            List the package recipes and its associated remotes
# add_ref             Associate a recipe's reference to a remote
# remove_ref          Dissociate a recipe's reference and its remote
# update_ref          Update the remote associated with a package recipe
# list_pref           List the package binaries and its associated remotes
# add_pref            Associate a package reference to a remote
# remove_pref         Dissociate a package's reference and its remote
# update_pref         Update the remote associated with a binary package
# clean               Clean the list of remotes and all recipe-remote


@conan_command(group="Misc commands")
def remote(*args, conan_api, parser, **kwargs):
    """
    Manages the remote list and the package recipes associated with a remote.
    """
    return
