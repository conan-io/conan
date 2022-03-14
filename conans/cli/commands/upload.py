from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.client.userio import UserInput
from conans.errors import ConanException


@conan_command(group=COMMAND_GROUPS['creator'])
def upload(conan_api: ConanAPIV2, parser, *args):
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
    conan_api.upload.upload_bundle(upload_bundle, remote)


def _ask_confirm_upload(conan_api, upload_data):
    ui = UserInput(conan_api.config.get("core:non_interactive"))
    for recipe in upload_data.recipes:
        msg = "Are you sure you want to upload recipe '%s'?" % recipe.ref.repr_notime()
        if not ui.request_boolean(msg):
            recipe.upload = False
            for package in recipe.packages:
                package.upload = False
        else:
            for package in recipe.packages:
                msg = "Are you sure you want to upload package '%s'?" % package.pref.repr_notime()
                if not ui.request_boolean(msg):
                    package.upload = False
