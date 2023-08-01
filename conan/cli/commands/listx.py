import copy

from conan.api.conan_api import ConanAPI
from conan.api.model import MultiPackagesList, PackagesList
from conan.cli import make_abs_path
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands.list import print_list_text, print_list_json
from conan.cli.formatters.list import list_packages_html


@conan_command(group="Consumer")
def listx(conan_api: ConanAPI, parser, *args):
    """
    Several operations over package lists
    """


@conan_subcommand(formatters={"text": print_list_text,
                              "json": print_list_json,
                              "html": list_packages_html})
def listx_find_remote(conan_api, parser, subparser, *args):
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
    selected_remotes = conan_api.remotes.list(args.remote)

    result = MultiPackagesList()
    for ref, recipe_bundle in package_list.refs():
        for r in selected_remotes:
            ref_no_rev = copy.copy(ref)  # TODO: Improve ugly API
            ref_no_rev.revision = None
            revs = conan_api.list.recipe_revisions(ref_no_rev, remote=r)
            if ref in revs:
                # found
                result.setdefault(r.name, PackagesList()).add_refs([ref])
                break

        for pref, _ in package_list.prefs(ref, recipe_bundle):
            for r in selected_remotes:
                pref_no_rev = copy.copy(pref)  # TODO: Improve ugly API
                pref_no_rev.revision = None
                prevs = conan_api.list.package_revisions(pref_no_rev, remote=r)
                if pref in prevs:
                    # found
                    result.setdefault(r.name, PackagesList()).add_prefs(ref, [pref])
                    break

    return {
        "results": result.serialize(),
        "conan_api": conan_api,
        "cli_args": " ".join([f"{arg}={getattr(args, arg)}" for arg in vars(args) if getattr(args, arg)])
    }
