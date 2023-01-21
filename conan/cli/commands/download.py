from multiprocessing.pool import ThreadPool

from conan.api.conan_api import ConanAPI
from conan.api.output import ConanOutput
from conan.cli.command import conan_command, OnceArgument
from conan.internal.api.select_pattern import SelectPattern
from conans.errors import ConanException


@conan_command(group="Creator")
def download(conan_api: ConanAPI, parser, *args):
    """
    Download a conan package from a remote server, by its reference. It downloads just the package,
    but not its transitive dependencies, and it will not call any generate, generators or deployers.
    It can download multiple packages if patterns are used, and also queries over the package
    binaries can be provided.
    """

    parser.add_argument('reference', help="Recipe reference or package reference, can contain * as "
                                          "wildcard at any reference field. If revision is not "
                                          "specified, it is assumed latest one.")
    parser.add_argument("--only-recipe", action='store_true', default=False,
                        help='Download only the recipe/s, not the binary packages.')
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="Only upload packages matching a specific query. e.g: os=Windows AND "
                             "(arch=x86 OR compiler=gcc)")
    parser.add_argument("-r", "--remote", action=OnceArgument, required=True,
                        help='Download from this specific remote')

    args = parser.parse_args(*args)
    remote = conan_api.remotes.get(args.remote)
    parallel = conan_api.config.get("core.download:parallel", default=1, check_type=int)
    ref_pattern = SelectPattern(args.reference)
    if args.only_recipe:
        if ref_pattern.package_id:
            raise ConanException("Do not specify 'package_id' with 'only-recipe'")
    else:
        ref_pattern.package_id = ref_pattern.package_id or "*"
    select_bundle = conan_api.list.select(ref_pattern, args.package_query, remote)
    refs = []
    prefs = []
    for ref, recipe_bundle in select_bundle.refs():
        refs.append(ref)
        for pref, _ in select_bundle.prefs(ref, recipe_bundle):
            prefs.append(pref)

    if parallel <= 1:
        for ref in refs:
            conan_api.download.recipe(ref, remote)
        for pref in prefs:
            conan_api.download.package(pref, remote)
    else:
        _download_parallel(parallel, conan_api, refs, prefs, remote)


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
