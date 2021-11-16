import os

from conans.cli.command import conan_command, Extender, COMMAND_GROUPS, OnceArgument
from conans.cli.commands.common import _add_common_install_arguments, _help_build_policies
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
    parser.add_argument("path_or_reference", help="Path to a folder containing a recipe"
                                                  " (conanfile.py or conanfile.txt) or to a recipe file. e.g., "
                                                  "./my_project/conanfile.txt. It could also be a reference")
    parser.add_argument("reference", nargs="?",
                        help='Reference for the conanfile path of the first argument: '
                             'user/channel, version@user/channel or pkg/version@user/channel'
                             '(if name or version declared in conanfile.py, they should match)')
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

    profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                options=args.options_build, env=args.env_build,
                                conf=args.conf_build)
    # TODO: 2.0 create profile_host object here to avoid passing a lot of arguments to the API

    cwd = os.getcwd()

    # We need @ otherwise it could be a path, so check strict
    path_is_reference = check_valid_ref(args.path_or_reference)

    info = None
    try:
        if not path_is_reference:
            name, version, user, channel, _ = get_reference_fields(args.reference,
                                                                   user_channel_input=True)
            info = conan_api.install.install(path=args.path_or_reference,
                                             name=name, version=version, user=user, channel=channel,
                                             settings=args.settings_host, options=args.options_host,
                                             env=args.env_host, profile_names=args.profile_host,
                                             conf=args.conf_host,
                                             profile_build=profile_build,
                                             remote_name=args.remote,
                                             build=args.build,
                                             update=args.update, generators=args.generator,
                                             no_imports=args.no_imports,
                                             install_folder=args.install_folder,
                                             lockfile=args.lockfile,
                                             lockfile_out=args.lockfile_out,
                                             require_overrides=args.require_override)
        else:
            if args.reference:
                raise ConanException("A full reference was provided as first argument, second "
                                     "argument not allowed")

            ref = RecipeReference.loads(args.path_or_reference)
            info = conan_api.install.install_reference(ref,
                                                       settings=args.settings_host,
                                                       options=args.options_host,
                                                       env=args.env_host,
                                                       conf=args.conf_host,
                                                       profile_names=args.profile_host,
                                                       profile_build=profile_build,
                                                       remote_name=args.remote,
                                                       build=args.build,
                                                       update=args.update,
                                                       generators=args.generator,
                                                       install_folder=args.install_folder,
                                                       lockfile=args.lockfile,
                                                       lockfile_out=args.lockfile_out,
                                                       is_build_require=args.build_require,
                                                       require_overrides=args.require_override)

    except ConanException as exc:
        info = exc.info
        raise
