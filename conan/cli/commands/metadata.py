import os
import shutil

from conan.cli.command import conan_command, conan_subcommand
from conan.internal.conan_app import ConanApp
from conans.model.recipe_ref import RecipeReference


@conan_command(group='Misc')
def metadata(conan_api, parser, *args):
    """
    Manage the recipes and packages metadata files
    """


@conan_subcommand()
def metadata_add(conan_api, parser, subparser, *args):
    """
    Add metadata to packages in cache
    """
    subparser.add_argument("ref", help="reference of recipe or package binary")
    subparser.add_argument("-s", "--src", help='File or folder to add')
    subparser.add_argument("-d", "--dst", help='Folder inside metadata')
    args = parser.parse_args(*args)

    app = ConanApp(conan_api.cache_folder)
    ref = RecipeReference.loads(args.ref)
    if ref.revision is None:
        ref = app.cache.get_latest_recipe_reference(ref)
    folder = app.cache.ref_layout(ref).metadata()
    shutil.copytree(args.src, os.path.join(folder, args.dst, args.src))
