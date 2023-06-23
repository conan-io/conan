import json

from conan.api.conan_api import ConanAPI
from conan.api.model import ListPattern, MultiPackagesList
from conan.api.output import Color, cli_out_write
from conan.cli import make_abs_path
from conan.cli.command import conan_command, OnceArgument, conan_subcommand
from conan.cli.commands.list import print_list_text, print_list_json
from conan.cli.formatters.list import list_packages_html
from conans.errors import ConanException
from conans.util.dates import timestamp_to_str


@conan_command(group="Consumer")
def listq(conan_api: ConanAPI, parser, *args):
    """
    Several operations over package lists
    """


@conan_subcommand(formatters={"text": print_list_text,
                              "json": print_list_json,
                              "html": list_packages_html})
def listq_remote(conan_api, parser, subparser, *args):
    """
    Compute the build order of a dependency graph.
    """
    subparser.add_argument('list', help="Input package list")
    subparser.add_argument("-r", "--remote", default=None, action="append",
                           help="Remote names. Accepts wildcards ('*' means all the remotes available)")
    args = parser.parse_args(*args)

    listfile = make_abs_path(args.list)
    multi_pkglist = MultiPackagesList.load(listfile)
    package_list = multi_pkglist["Local Cache"]
    for ref, recipe_bundle in package_list.refs():
        # FIXME: Need a better way to check for existing of a given revision in the server
        for r in selected_remotes:
            revs = conan_api.list.recipe_revisions(ref, remote=r)
            if ref in revs:
                # found
                multi_pkglist[r.name] = recipe_bundle

        for pref, _ in package_list.prefs(ref, recipe_bundle):
            prefs.append(pref)

    return {
        "results": pkglist.serialize(),
        "conan_api": conan_api,
        "cli_args": " ".join([f"{arg}={getattr(args, arg)}" for arg in vars(args) if getattr(args, arg)])
    }
