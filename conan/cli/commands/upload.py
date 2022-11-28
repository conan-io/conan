from conan.api.conan_api import ConanAPI
from conan.cli.command import conan_command, OnceArgument
from conans.client.userio import UserInput
from conans.errors import ConanException


@conan_command(group="Creator")
def upload(conan_api: ConanAPI, parser, *args):
    """
    Uploads a recipe and binary packages to a remote.
    By default, all the matching references are uploaded (all revisions).
    By default, if a recipe reference is specified, it will upload all the revisions for all the
    binary packages, unless --only-recipe is specified. You can use the "latest" placeholder at the
    "reference" argument to specify the latest revision of the recipe or the package.
    """
    parser.add_argument('reference', help="Recipe reference or package reference, can contain * as "
                                          "wildcard at any reference field. If no revision is "
                                          "specified, it is assumed to be the latest")
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

    args = parser.parse_args(*args)

    remote = conan_api.remotes.get(args.remote)
    enabled_remotes = conan_api.remotes.list()

    upload_bundle = conan_api.upload.get_bundle(args.reference, args.package_query, args.only_recipe)
    if not upload_bundle.recipes:
        raise ConanException("No recipes found matching pattern '{}'".format(args.reference))

    if args.check:
        conan_api.upload.check_integrity(upload_bundle)

    # Check if the recipes/packages are in the remote
    conan_api.upload.check_upstream(upload_bundle, remote, args.force)

    # If only if search with "*" we ask for confirmation
    if not args.confirm and "*" in args.reference:
        _ask_confirm_upload(conan_api, upload_bundle)

    if not upload_bundle.any_upload:
        return

    conan_api.upload.prepare(upload_bundle, enabled_remotes)
    conan_api.upload.upload_bundle(upload_bundle, remote)


def _ask_confirm_upload(conan_api, upload_data):
    ui = UserInput(conan_api.config.get("core:non_interactive"))
    for ref, bundle in upload_data.recipes.items():
        msg = "Are you sure you want to upload recipe '%s'?" % ref.repr_notime()
        if not ui.request_boolean(msg):
            bundle.upload = False
            for package in bundle.packages:
                package.upload = False
        else:
            for package in bundle.packages:
                msg = "Are you sure you want to upload package '%s'?" % package.pref.repr_notime()
                if not ui.request_boolean(msg):
                    package.upload = False
