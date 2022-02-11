import os
from collections import namedtuple

from conans import __version__ as client_version
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.conf.required_version import check_required_conan_version
from conans.client.migrations import ClientMigrator
from conans.client.profile_loader import ProfileLoader
from conans.client.source import config_source_local
from conans.errors import (ConanException)
from conans.model.graph_lock import LOCKFILE, Lockfile
from conans.model.recipe_ref import RecipeReference
from conans.model.version import Version
from conans.paths import get_conan_user_home
from conans.util.files import mkdir


class ProfileData(namedtuple("ProfileData", ["profiles", "settings", "options", "env", "conf"])):
    def __bool__(self):
        return bool(self.profiles or self.settings or self.options or self.env or self.conf)


def _make_abs_path(path, cwd=None, default=None):
    """convert 'path' to absolute if necessary (could be already absolute)
    if not defined (empty, or None), will return 'default' one or 'cwd'
    """
    cwd = cwd or os.getcwd()
    if not path:
        abs_path = default or cwd
    elif os.path.isabs(path):
        abs_path = path
    else:
        abs_path = os.path.normpath(os.path.join(cwd, path))
    return abs_path


def _get_conanfile_path(path, cwd, py):
    """
    param py= True: Must be .py, False: Must be .txt, None: Try .py, then .txt
    """
    candidate_paths = list()
    path = _make_abs_path(path, cwd)

    if os.path.isdir(path):  # Can be a folder
        if py:
            path = os.path.join(path, "conanfile.py")
            candidate_paths.append(path)
        elif py is False:
            path = os.path.join(path, "conanfile.txt")
            candidate_paths.append(path)
        else:
            path_py = os.path.join(path, "conanfile.py")
            candidate_paths.append(path_py)
            if os.path.exists(path_py):
                path = path_py
            else:
                path = os.path.join(path, "conanfile.txt")
                candidate_paths.append(path)
    else:
        candidate_paths.append(path)

    if not os.path.isfile(path):  # Must exist
        raise ConanException("Conanfile not found at %s" % " or ".join(candidate_paths))

    if py and not path.endswith(".py"):
        raise ConanException("A conanfile.py is needed, " + path + " is not acceptable")

    return path


class ConanAPIV1(object):

    def __init__(self, cache_folder=None):
        self.cache_folder = cache_folder or get_conan_user_home()
        # Migration system
        migrator = ClientMigrator(self.cache_folder, Version(client_version))
        migrator.migrate()
        check_required_conan_version(self.cache_folder)

    @api_method
    def source(self, path, source_folder=None, cwd=None):
        app = ConanApp(self.cache_folder)

        cwd = cwd or os.getcwd()
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        source_folder = _make_abs_path(source_folder, cwd)

        mkdir(source_folder)

        # only infos if exist
        conanfile = app.graph_manager.load_consumer_conanfile(conanfile_path)
        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_package(None)

        config_source_local(conanfile, conanfile_path, app.hook_manager)


def get_graph_info(profile_host, profile_build, cwd, cache,
                   name=None, version=None, user=None, channel=None, lockfile=None):

    root_ref = RecipeReference(name, version, user, channel)

    graph_lock = None
    if lockfile:
        lockfile = lockfile if os.path.isfile(lockfile) else os.path.join(lockfile, LOCKFILE)
        graph_lock = Lockfile.load(lockfile)
        ConanOutput().info("Using lockfile: '{}'".format(lockfile))

    profile_loader = ProfileLoader(cache)
    profiles = [profile_loader.get_default_host()] if not profile_host.profiles \
        else profile_host.profiles
    phost = profile_loader.from_cli_args(profiles, profile_host.settings,
                                         profile_host.options, profile_host.env,
                                         profile_host.conf, cwd)

    profiles = [profile_loader.get_default_build()] if not profile_build.profiles \
        else profile_build.profiles
    # Only work on the profile_build if something is provided
    pbuild = profile_loader.from_cli_args(profiles, profile_build.settings,
                                          profile_build.options, profile_build.env,
                                          profile_build.conf, cwd)

    # Apply the new_config to the profiles the global one, so recipes get it too
    # TODO: This means lockfiles contain whole copy of the config here?
    # FIXME: Apply to locked graph-info as well
    phost.conf.rebase_conf_definition(cache.new_config)
    pbuild.conf.rebase_conf_definition(cache.new_config)
    return phost, pbuild, graph_lock, root_ref
