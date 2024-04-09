import copy

from conan.api.conan_api import ConanAPI
from conan.api.model import MultiPackagesList, PackagesList
from conan.cli import make_abs_path
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands.list import print_list_text, print_list_json
from conan.cli.formatters.list import list_packages_html
from conans.errors import NotFoundException


@conan_command(group="Consumer")
def pkglist(conan_api: ConanAPI, parser, *args):  # noqa
    """
    Several operations over package lists
    """


@conan_subcommand(formatters={"text": print_list_text,
                              "json": print_list_json,
                              "html": list_packages_html})
def pkglist_find_remote(conan_api, parser, subparser, *args):
    """
    (Experimental) Find the remotes of a list of packages in the cache
    """
    subparser.add_argument('list', help="Input package list")
    subparser.add_argument("-r", "--remote", default=None, action="append",
                           help="Remote names. Accepts wildcards "
                                "('*' means all the remotes available)")
    args = parser.parse_args(*args)

    listfile = make_abs_path(args.list)
    multi_pkglist = MultiPackagesList.load(listfile)
    package_list = multi_pkglist["Local Cache"]
    selected_remotes = conan_api.remotes.list(args.remote)

    result = MultiPackagesList()
    for r in selected_remotes:
        result_pkg_list = PackagesList()
        for ref, recipe_bundle in package_list.refs().items():
            ref_no_rev = copy.copy(ref)  # TODO: Improve ugly API
            ref_no_rev.revision = None
            try:
                revs = conan_api.list.recipe_revisions(ref_no_rev, remote=r)
            except NotFoundException:
                continue
            if ref not in revs:  # not found
                continue
            result_pkg_list.add_refs([ref])
            for pref, pref_bundle in package_list.prefs(ref, recipe_bundle).items():
                pref_no_rev = copy.copy(pref)  # TODO: Improve ugly API
                pref_no_rev.revision = None
                try:
                    prevs = conan_api.list.package_revisions(pref_no_rev, remote=r)
                except NotFoundException:
                    continue
                if pref in prevs:
                    result_pkg_list.add_prefs(ref, [pref])
                    info = recipe_bundle["packages"][pref.package_id]["info"]
                    result_pkg_list.add_configurations({pref: info})
        if result_pkg_list.recipes:
            result.add(r.name, result_pkg_list)

    return {
        "results": result.serialize(),
        "conan_api": conan_api,
        "cli_args": " ".join([f"{arg}={getattr(args, arg)}"
                              for arg in vars(args) if getattr(args, arg)])
    }


@conan_subcommand(formatters={"text": print_list_text,
                              "json": print_list_json,
                              "html": list_packages_html})
def pkglist_merge(conan_api, parser, subparser, *args):
    """
    (Experimental) Merge several package lists into a single one
    """
    subparser.add_argument("-l", "--list", help="Package list file", action="append")
    args = parser.parse_args(*args)

    result = MultiPackagesList()
    for pkglist in args.list:
        listfile = make_abs_path(pkglist)
        multi_pkglist = MultiPackagesList.load(listfile)
        result.merge(multi_pkglist)

    return {
        "results": result.serialize(),
        "conan_api": conan_api,
        "cli_args": " ".join([f"{arg}={getattr(args, arg)}"
                              for arg in vars(args) if getattr(args, arg)])
    }
