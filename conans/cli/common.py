import os

from conans.cli.command import Extender, OnceArgument, ExtenderValueRequired
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.model.graph_lock import LOCKFILE, Lockfile

_help_build_policies = '''Optional, specify which packages to build from source. Combining multiple
    '--build' options on one command line is allowed. For dependencies, the optional 'build_policy'
    attribute in their conanfile.py takes precedence over the command line parameter.
    Possible parameters:

    --build="*"        Force build for all packages, do not use binary packages.
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


def add_reference_args(parser):
    parser.add_argument("--name", action=OnceArgument,
                        help='Provide a package name if not specified in conanfile')
    parser.add_argument("--version", action=OnceArgument,
                        help='Provide a package version if not specified in conanfile')
    parser.add_argument("--user", action=OnceArgument,
                        help='Provide a user if not specified in conanfile')
    parser.add_argument("--channel", action=OnceArgument,
                        help='Provide a channel if not specified in conanfil')


def add_profiles_args(parser):
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

    def options_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-o{}".format(short_suffix),
                            "--options{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest="options_{}".format(machine),
                            help='Define options values ({} machine), e.g.:'
                                 ' -o{} Pkg:with_qt=true'.format(machine, short_suffix))

    def conf_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-c{}".format(short_suffix),
                            "--conf{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest='conf_{}'.format(machine),
                            help='Configuration to build the package, overwriting the defaults'
                                 ' ({} machine). e.g.: -c{} '
                                 'tools.cmake.cmaketoolchain:generator=Xcode'.format(machine,
                                                                                     short_suffix))

    for item_fn in [options_args, profile_args, settings_args, conf_args]:
        item_fn("host", "",
                "")  # By default it is the HOST, the one we are building binaries for
        item_fn("build", ":b", ":build")
        item_fn("host", ":h", ":host")


def _add_common_install_arguments(parser, build_help, update_help=None):
    if build_help:
        parser.add_argument("-b", "--build", action=ExtenderValueRequired, nargs="?", help=build_help)

    parser.add_argument("-r", "--remote", action=Extender, default=None,
                        help='Look in the specified remote or remotes server')

    if not update_help:
        update_help = ("Will check the remote and in case a newer version and/or revision of "
                       "the dependencies exists there, it will install those in the local cache. "
                       "When using version ranges, it will install the latest version that "
                       "satisfies the range. Also, if using revisions, it will update to the "
                       "latest revision for the resolved version range.")

    parser.add_argument("-u", "--update", action='store_true', default=False,
                        help=update_help)
    add_profiles_args(parser)


def add_lockfile_args(parser):
    parser.add_argument("-l", "--lockfile", action=OnceArgument,
                        help="Path to a lockfile.")
    parser.add_argument("--lockfile-strict", action="store_true",
                        help="Raise an error if some dependency is not found in lockfile")
    parser.add_argument("--lockfile-out", action=OnceArgument,
                        help="Filename of the updated lockfile")
    parser.add_argument("--lockfile-packages", action="store_true",
                        help="Lock package-id and package-revision information")


def get_profiles_from_args(conan_api, args):
    build = [
        conan_api.profiles.get_default_build()] if not args.profile_build else args.profile_build
    host = [conan_api.profiles.get_default_host()] if not args.profile_host else args.profile_host

    profile_build = conan_api.profiles.get_profile(profiles=build, settings=args.settings_build,
                                                   options=args.options_build, conf=args.conf_build)
    profile_host = conan_api.profiles.get_profile(profiles=host, settings=args.settings_host,
                                                  options=args.options_host, conf=args.conf_host)
    return profile_host, profile_build


def get_remote_selection(conan_api, remote_patterns):
    """
    Return a list of Remote() objects matching the specified patterns. If a pattern doesn't match
    anything, it fails
    """
    ret_remotes = []
    for pattern in remote_patterns:
        tmp = conan_api.remotes.list(pattern=pattern, only_active=True)
        if not tmp:
            raise ConanException("Remotes for pattern '{}' can't be found or are "
                                 "disabled".format(pattern))
        ret_remotes.extend(tmp)
    return ret_remotes


def get_lockfile(lockfile, strict=False):
    graph_lock = None
    if lockfile:
        lockfile = lockfile if os.path.isfile(lockfile) else os.path.join(lockfile, LOCKFILE)
        graph_lock = Lockfile.load(lockfile)
        graph_lock.strict = strict
        ConanOutput().info("Using lockfile: '{}'".format(lockfile))
    return graph_lock


def get_multiple_remotes(conan_api, remote_names=None):
    if remote_names:
        return [conan_api.remotes.get(remote_name) for remote_name in remote_names]
    elif remote_names is None:
        # if we don't pass any remotes we want to retrieve only the enabled ones
        return conan_api.remotes.list(only_active=True)


def scope_options(profile, requires, tool_requires):
    """
    Command line helper to scope options when ``command -o myoption=myvalue`` is used,
    that needs to be converted to "-o pkg:myoption=myvalue". The "pkg" value will be
    computed from the given requires/tool_requires
    """
    # FIXME: This helper function here is not great, find a better place
    if requires and len(requires) == 1 and not tool_requires:
        profile.options.scope(requires[0])
    if tool_requires and len(tool_requires) == 1 and not requires:
        profile.options.scope(tool_requires[0])
