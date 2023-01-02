import os

from conan.api.output import ConanOutput
from conan.cli.command import conan_command, conan_subcommand
from conan.cli.commands import make_abs_path
from conan.internal.conan_app import ConanApp
from conans.model.recipe_ref import RecipeReference


@conan_command(group="Creator")
def editable(conan_api, parser, *args):
    """
    Allows working with a package in user folder
    """


@conan_subcommand()
def editable_add(conan_api, parser, subparser, *args):
    """
    Define the given <path> location as the package <reference>, so when this
    package is required, it is used from this <path> location instead of from the cache
    """
    subparser.add_argument('path', help='Path to the package folder in the user workspace')
    subparser.add_argument('reference', help='Package reference e.g.: mylib/1.X@user/channel')
    subparser.add_argument("-of", "--output-folder",
                           help='The root output folder for generated and build files')
    args = parser.parse_args(*args)

    path = args.path
    reference = args.reference
    cwd = os.getcwd()

    # TODO: Decide in which API we put this
    app = ConanApp(conan_api.cache_folder)
    # Retrieve conanfile.py from target_path
    target_path = conan_api.local.get_conanfile_path(path=path, cwd=cwd, py=True)
    output_folder = make_abs_path(args.output_folder) if args.output_folder else None
    # Check the conanfile is there, and name/version matches
    ref = RecipeReference.loads(reference)
    app.cache.editable_packages.add(ref, target_path, output_folder=output_folder)
    ConanOutput().success("Reference '{}' in editable mode".format(reference))


@conan_subcommand()
def editable_remove(conan_api, parser, subparser, *args):
    """
    Remove the "editable" mode for this reference.
    """
    subparser.add_argument('reference', help='Package reference e.g.: mylib/1.X@user/channel')
    args = parser.parse_args(*args)

    app = ConanApp(conan_api.cache_folder)
    ref = RecipeReference.loads(args.reference)
    ret = app.cache.editable_packages.remove(ref)
    out = ConanOutput()
    if ret:
        out.success("Removed editable mode for reference '{}'".format(ref))
    else:
        out.warning("Reference '{}' was not installed as editable".format(ref))


@conan_subcommand()
def editable_list(conan_api, parser, subparser, *args):
    """
    List packages in editable mode
    """
    app = ConanApp(conan_api.cache_folder)
    result = {str(k): v for k, v in app.cache.editable_packages.edited_refs.items()}

    app = ConanApp(conan_api.cache_folder)
    out = ConanOutput()
    for k, v in app.cache.editable_packages.edited_refs.items():
        out.info("%s" % k)
        out.info("    Path: %s" % v["path"])
    return result
