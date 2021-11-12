import os

from conans.cli.command import conan_command, Extender, COMMAND_GROUPS, OnceArgument
from conans.client.conan_api import ProfileData
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.model.ref import check_valid_ref, get_reference_fields

_help_build_policies = '''Optional, specify which packages to build from source. Combining multiple
    '--build' options on one command line is allowed. For dependencies, the optional 'build_policy'
    attribute in their conanfile.py takes precedence over the command line parameter.
    Possible parameters:

    --build            Force build for all packages, do not use binary packages.
    --build=never      Disallow build for all packages, use binary packages or fail if a binary
                       package is not found. Cannot be combined with other '--build' options.
    --build=missing    Build packages from source whose binary package is not found.
    --build=cascade    Build packages from source that have at least one dependency being built from
                       source.
    --build=[pattern]  Build packages from source whose package reference matches the pattern. The
                       pattern uses 'fnmatch' style wildcards.
    --build=![pattern] Excluded packages, which will not be built from the source, whose package
                       reference matches the pattern. The pattern uses 'fnmatch' style wildcards.

    Default behavior: If you omit the '--build' option, the 'build_policy' attribute in conanfile.py
    will be used if it exists, otherwise the behavior is like '--build={}'.
'''


def _add_profile_arguments(parser):
    # Arguments that can apply to the build or host machines (easily extend to target machine)
    def environment_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-e{}".format(short_suffix),
                            "--env{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest="env_{}".format(machine),
                            help='Environment variables that will be set during the'
                                 ' package build ({} machine).'
                                 ' e.g.: -e{} CXX=/usr/bin/clang++'.format(machine, short_suffix))

    def options_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-o{}".format(short_suffix),
                            "--options{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest="options_{}".format(machine),
                            help='Define options values ({} machine), e.g.:'
                                 ' -o{} Pkg:with_qt=true'.format(machine, short_suffix))

    def profile_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-pr{}".format(short_suffix),
                            "--profile{}".format(long_suffix),
                            default=None, action=Extender,
                            dest='profile_{}'.format(machine),
                            help='Apply the specified profile to the {} machine'.format(machine))

    def settings_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-s{}".format(short_suffix),
                            "--settings{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest='settings_{}'.format(machine),
                            help='Settings to build the package, overwriting the defaults'
                                 ' ({} machine). e.g.: -s{} compiler=gcc'.format(machine,
                                                                                 short_suffix))

    def conf_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-c{}".format(short_suffix),
                            "--conf{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest='conf_{}'.format(machine),
                            help='Configuration to build the package, overwriting the defaults'
                                 ' ({} machine). e.g.: -c{} '
                                 'tools.cmake.cmaketoolchain:generator=Xcode'.format(machine,
                                                                                     short_suffix))

    for item_fn in [environment_args, options_args, profile_args, settings_args, conf_args]:
        item_fn("host", "", "")  # By default it is the HOST, the one we are building binaries for
        item_fn("build", ":b", ":build")
        item_fn("host", ":h", ":host")


def _add_common_install_arguments(parser, build_help, update_help=None, lockfile=True):
    if build_help:
        parser.add_argument("-b", "--build", action=Extender, nargs="?", help=build_help)

    parser.add_argument("-r", "--remote", action=OnceArgument,
                        help='Look in the specified remote server')

    if not update_help:
        update_help = ("Will check the remote and in case a newer version and/or revision of "
                       "the dependencies exists there, it will install those in the local cache. "
                       "When using version ranges, it will install the latest version that "
                       "satisfies the range. Also, if using revisions, it will update to the "
                       "latest revision for the resolved version range.")

    parser.add_argument("-u", "--update", action='store_true', default=False,
                        help=update_help)
    if lockfile:
        parser.add_argument("-l", "--lockfile", action=OnceArgument,
                            help="Path to a lockfile")
        parser.add_argument("--lockfile-out", action=OnceArgument,
                            help="Filename of the updated lockfile")
    _add_profile_arguments(parser)


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
        raise
