import os

from conans.cli.command import conan_command, Extender, COMMAND_GROUPS, OnceArgument
from conans.cli.common import _add_common_install_arguments, _help_build_policies
from conans.client.conan_api import ProfileData
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.model.ref import check_valid_ref, get_reference_fields


@conan_command(group=COMMAND_GROUPS['consumer'])
def install(conan_api, parser, *args, **kwargs):
    """
    Installs the requirements specified in a recipe (conanfile.py or conanfile.txt).

    It can also be used to install a concrete package specifying a
    reference. If any requirement is not found in the local cache, it will
    retrieve the recipe from a remote, looking for it sequentially in the
    configured remotes. When the recipes have been downloaded it will try
    to download a binary package matching the specified settings, only from
    the remote from which the recipe was retrieved. If no binary package is
    found, it can be built from sources using the '--build' option. When
    the package is installed, Conan will write the files for the specified
    generators.
    """
    parser.add_argument("path", nargs="?", help="Path to a conanfile, including filename, "
                                                "like 'path/conanfile.py'")

    parser.add_argument("--reference", action=OnceArgument,
                        help='Provide a package reference instead of a conanfile')

    parser.add_argument("-g", "--generator", nargs=1, action=Extender,
                        help='Generators to use')
    parser.add_argument("-if", "--install-folder", action=OnceArgument,
                        help='Use this directory as the directory where to put the generator'
                             'files.')

    parser.add_argument("--no-imports", action='store_true', default=False,
                        help='Install specified packages but avoid running imports')
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='The provided reference is a build-require')

    _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
    parser.add_argument("--require-override", action="append",
                        help="Define a requirement override")

    args = parser.parse_args(*args)
    env = None  # TODO: Not handling environment
    profile_host = ProfileData(profiles=args.profile_host, settings=args.settings_host,
                               options=args.options_host, env=env,
                               conf=args.conf_host)

    profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                options=args.options_build, env=env,
                                conf=args.conf_build)

    cwd = os.getcwd()

    info = None
    try:
        info = conan_api.install.install_(path=os.path.join(cwd, args.path),
                                         reference=args.reference,
                                         profile_host=profile_host,
                                         profile_build=profile_build,
                                         remote_name=args.remote,
                                         build=args.build,
                                         update=args.update,
                                         generators=args.generator,
                                         no_imports=args.no_imports,
                                         install_folder=args.install_folder,
                                         lockfile=args.lockfile,
                                         lockfile_out=args.lockfile_out,
                                         is_build_require=args.build_require,
                                         require_overrides=args.require_override)
    except ConanException as exc:
        info = exc.info
        raise
