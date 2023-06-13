from conan.api.conan_api import ConanAPI
from conan.api.model import ListPattern, MultiPackagesList
from conan.cli import make_abs_path
from conan.cli.command import conan_command, OnceArgument
from conans.client.userio import UserInput
from conan.errors import ConanException


@conan_command(group="Creator")
def upload(conan_api: ConanAPI, parser, *args):
    """
    Upload packages to a remote.

    By default, all the matching references are uploaded (all revisions).
    By default, if a recipe reference is specified, it will upload all the revisions for all the
    binary packages, unless --only-recipe is specified. You can use the "latest" placeholder at the
    "reference" argument to specify the latest revision of the recipe or the package.
    """
    parser.add_argument('pattern', nargs="?",
                        help="A pattern in the form 'pkg/version#revision:package_id#revision', "
                             "e.g: zlib/1.2.13:* means all binaries for zlib/1.2.13. "
                             "If revision is not specified, it is assumed latest one.")
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="Only upload packages matching a specific query. e.g: os=Windows AND "
                             "(arch=x86 OR compiler=gcc)")
    # using required, we may want to pass this as a positional argument?
    parser.add_argument("-r", "--remote", action=OnceArgument, required=True,
                        help='Upload to this specific remote')
    parser.add_argument("--only-recipe", action='store_true', default=False,
                        help='Upload only the recipe/s, not the binary packages.')
    parser.add_argument("--force", action='store_true', default=False,
                        help='Force the upload of the artifacts even if the revision already exists'
                             ' in the server')
    parser.add_argument("--check", action='store_true', default=False,
                        help='Perform an integrity check, using the manifests, before upload')
    parser.add_argument('-c', '--confirm', default=False, action='store_true',
                        help='Upload all matching recipes without confirmation')
    parser.add_argument("-l", "--list", help="Package list file")
    parser.add_argument("-m", "--metadata", action='append',
                        help='Upload the metadata, even if the package is already in the server and '
                             'not uploaded')

    args = parser.parse_args(*args)

    remote = conan_api.remotes.get(args.remote)
    enabled_remotes = conan_api.remotes.list()

    if args.pattern is None and args.list is None:
        raise ConanException("Missing pattern or package list file")
    if args.pattern and args.list:
        raise ConanException("Cannot define both the pattern and the package list file")
    if args.list:
        listfile = make_abs_path(args.list)
        multi_package_list = MultiPackagesList.load(listfile)
        package_list = multi_package_list["Local Cache"]
    else:
        ref_pattern = ListPattern(args.pattern, package_id="*", only_recipe=args.only_recipe)
        package_list = conan_api.list.select(ref_pattern, package_query=args.package_query)

    if not package_list.recipes:
        raise ConanException("No recipes found matching pattern '{}'".format(args.pattern))

    if args.check:
        conan_api.cache.check_integrity(package_list)
    # Check if the recipes/packages are in the remote
    conan_api.upload.check_upstream(package_list, remote, args.force)

    # If only if search with "*" we ask for confirmation
    if not args.list and not args.confirm and "*" in args.pattern:
        _ask_confirm_upload(conan_api, package_list)

    conan_api.upload.prepare(package_list, enabled_remotes, args.metadata)
    conan_api.upload.upload(package_list, remote)

    conan_api.upload.upload_backup_sources(package_list)


def _ask_confirm_upload(conan_api, upload_data):
    ui = UserInput(conan_api.config.get("core:non_interactive"))
    for ref, bundle in upload_data.refs():
        msg = "Are you sure you want to upload recipe '%s'?" % ref.repr_notime()
        if not ui.request_boolean(msg):
            bundle["upload"] = False
            for _, prev_bundle in upload_data.prefs(ref, bundle):
                prev_bundle["upload"] = False

        else:
            for pref, prev_bundle in upload_data.prefs(ref, bundle):
                msg = "Are you sure you want to upload package '%s'?" % pref.repr_notime()
                if not ui.request_boolean(msg):
                    prev_bundle["upload"] = False
