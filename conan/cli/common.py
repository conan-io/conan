import os

from conan.api.output import ConanOutput
from conan.cli.commands import make_abs_path
from conans.errors import ConanException
from conans.model.graph_lock import LOCKFILE, Lockfile


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


def get_lockfile(lockfile_path, cwd, conanfile_path, partial=False):
    if lockfile_path == "None":
        # Allow a way with ``--lockfile=None`` to opt-out automatic usage of conan.lock
        return
    if lockfile_path is None:
        # if conanfile_path is defined, take it as reference
        base_path = os.path.dirname(conanfile_path) if conanfile_path else cwd
        lockfile_path = make_abs_path(LOCKFILE, base_path)
        if not os.path.isfile(lockfile_path):
            return
    else:
        lockfile_path = make_abs_path(lockfile_path, cwd)
        if not os.path.isfile(lockfile_path):
            raise ConanException("Lockfile doesn't exist: {}".format(lockfile_path))

    graph_lock = Lockfile.load(lockfile_path)
    graph_lock.partial = partial
    ConanOutput().info("Using lockfile: '{}'".format(lockfile_path))
    return graph_lock


def save_lockfile_out(args, graph, lockfile, cwd):
    if args.lockfile_out is None:
        return
    lockfile_out = make_abs_path(args.lockfile_out, cwd)
    if lockfile is None or args.lockfile_clean:
        lockfile = Lockfile(graph, args.lockfile_packages)
    else:
        lockfile.update_lock(graph, args.lockfile_packages)
    lockfile.save(lockfile_out)
    ConanOutput().info(f"Generated lockfile: {lockfile_out}")
    return lockfile


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
