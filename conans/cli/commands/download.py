from multiprocessing.pool import ThreadPool

from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.cli.output import ConanOutput
from conans.errors import ConanException


@conan_command(group=COMMAND_GROUPS['creator'])
def download(conan_api: ConanAPIV2, parser, *args):
    """
    Uploads a recipe and binary packages to a remote.
    By default, all the matching references are uploaded (all revisions).
    By default, if a recipe reference is specified, it will upload all the revisions for all the
    binary packages, unless --only-recipe is specified. You can use the "latest" placeholder at the
    "reference" argument to specify the latest revision of the recipe or the package.
    """
    _not_specified_ = object()

    parser.add_argument('reference', help="Recipe reference or package reference, can contain * as "
                                          "wildcard at any reference field. A placeholder 'latest'"
                                          "can be used in the revision fields: e.g: 'lib/*#latest'.")
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="Only upload packages matching a specific query. e.g: os=Windows AND "
                             "(arch=x86 OR compiler=gcc)")
    parser.add_argument("-r", "--remote", action=OnceArgument, required=True,
                        help='Upload to this specific remote')

    args = parser.parse_args(*args)
    remote = conan_api.remotes.get(args.remote)
    parallel = conan_api.config.get("core.download:parallel", default=1, check_type=int)
    if ":" in args.reference or args.package_query:

        # We are downloading the selected packages and the recipes belonging to these
        prefs = conan_api.search.package_revisions(args.reference, query=args.package_query,
                                                   remote=remote)
        if not prefs:
            raise ConanException("There are no packages matching '{}'".format(args.reference))
        refs = set([pref.ref for pref in prefs])
        if parallel <= 1:
            for ref in refs:
                conan_api.download.recipe(ref, remote)
            for pref in prefs:
                conan_api.download.package(pref, remote)
        else:
            _download_parallel(parallel, conan_api, refs, prefs, remote)

    else:
        refs = conan_api.search.recipe_revisions(args.reference, remote)
        if not refs:
            raise ConanException("There are no recipes matching '{}'".format(args.reference))
        if parallel <= 1:
            for ref in refs:
                conan_api.download.recipe(ref, remote)
        else:
            _download_parallel(parallel, conan_api, refs, [], remote)


def _download_parallel(parallel, conan_api, refs, prefs, remote):

    thread_pool = ThreadPool(parallel)
    # First the recipes in parallel, we have to make sure the recipes are downloaded before the
    # packages
    ConanOutput().info("Downloading recipes in %s parallel threads" % parallel)
    thread_pool.starmap(conan_api.download.recipe, [(ref, remote) for ref in refs])
    thread_pool.close()
    thread_pool.join()

    # Then the packages in parallel
    if prefs:
        thread_pool = ThreadPool(parallel)
        ConanOutput().info("Downloading binary packages in %s parallel threads" % parallel)
        thread_pool.starmap(conan_api.download.package,  [(pref, remote) for pref in prefs])
        thread_pool.close()
        thread_pool.join()

