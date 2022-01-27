import os
from collections import OrderedDict
from collections import namedtuple

from conans import __version__ as client_version
from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.cmd.build import cmd_build
from conans.client.cmd.download import download
from conans.client.conf.required_version import check_required_conan_version
from conans.client.importer import run_imports, undo_imports
from conans.client.manager import deps_install
from conans.client.migrations import ClientMigrator
from conans.client.profile_loader import ProfileLoader
from conans.client.source import config_source_local
from conans.errors import (ConanException, RecipeNotFoundException,
                           NotFoundException)
from conans.model.graph_lock import LOCKFILE, Lockfile
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.model.ref import check_valid_ref
from conans.model.version import Version
from conans.paths import get_conan_user_home
from conans.search.search import search_recipes
from conans.util.files import mkdir, load, discarded_file


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
    def download(self, reference, remote_name=None, packages=None, recipe=False):
        app = ConanApp(self.cache_folder)
        if packages and recipe:
            raise ConanException("recipe parameter cannot be used together with packages")
        # Install packages without settings (fixed ids or all)
        if check_valid_ref(reference):
            ref = RecipeReference.loads(reference)
            if packages and ref.revision is None:
                for package_id in packages:
                    if "#" in package_id:
                        raise ConanException("It is needed to specify the recipe revision if you "
                                             "specify a package revision")
            # FIXME: remote_name should be remote
            remotes = [Remote(remote_name, None)] if remote_name else None
            app.load_remotes(remotes)
            download(app, ref, packages, recipe)
        else:
            raise ConanException("Provide a valid full reference without wildcards.")

    @api_method
    def build(self, conanfile_path, name=None, version=None, user=None, channel=None,
              source_folder=None, package_folder=None, build_folder=None,
              install_folder=None, cwd=None, settings=None, options=None, env=None,
              remote_name=None, build=None, profile_names=None,
              update=False, generators=None, no_imports=False,
              lockfile=None, lockfile_out=None, profile_build=None, conf=None):

        app = ConanApp(self.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)])
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)

        cwd = cwd or os.getcwd()

        conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)
        build_folder = _make_abs_path(build_folder, cwd)
        install_folder = _make_abs_path(install_folder, cwd, default=build_folder)
        source_folder = _make_abs_path(source_folder, cwd, default=os.path.dirname(conanfile_path))
        default_pkg_folder = os.path.join(build_folder, "package")
        package_folder = _make_abs_path(package_folder, cwd, default=default_pkg_folder)

        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = \
                get_graph_info(profile_host, profile_build, cwd,
                               app.cache,
                               name=name, version=version, user=user, channel=channel,
                               lockfile=lockfile)
            deps_info = deps_install(app=app,
                                     ref_or_path=conanfile_path,
                                     install_folder=install_folder,
                                     base_folder=cwd,
                                     profile_host=profile_host,
                                     profile_build=profile_build,
                                     graph_lock=graph_lock,
                                     root_ref=root_ref,
                                     build_modes=build,
                                     generators=generators,
                                     no_imports=no_imports,
                                     conanfile_path=os.path.dirname(conanfile_path))

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock.save(lockfile_out)

            conanfile = deps_info.root.conanfile
            cmd_build(app, conanfile_path, conanfile, base_path=cwd,
                      source_folder=source_folder, build_folder=build_folder,
                      package_folder=package_folder, install_folder=install_folder)
        except ConanException as exc:
            raise

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

    @api_method
    def imports(self, conanfile_path, dest=None, cwd=None, settings=None,
                options=None, env=None, profile_names=None, profile_build=None, lockfile=None,
                conf=None):
        """
        :param path: Path to the conanfile
        :param dest: Dir to put the imported files. (Abs path or relative to cwd)
        :param cwd: Current working directory
        :return: None
        """
        app = ConanApp(self.cache_folder)
        app.load_remotes(update=False)
        cwd = cwd or os.getcwd()
        dest = _make_abs_path(dest, cwd)

        mkdir(dest)
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=None)

        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = \
                get_graph_info(profile_host, profile_build, cwd,
                               app.cache, lockfile=lockfile)

            deps_info = deps_install(app=app,
                                     ref_or_path=conanfile_path,
                                     install_folder=None,
                                     base_folder=cwd,
                                     profile_host=profile_host,
                                     profile_build=profile_build,
                                     graph_lock=graph_lock,
                                     root_ref=root_ref)
            conanfile = deps_info.root.conanfile
            conanfile.folders.set_base_imports(dest)
            return run_imports(conanfile)
        except ConanException as exc:
            raise

    @api_method
    def imports_undo(self, manifest_path):
        cwd = os.getcwd()
        manifest_path = _make_abs_path(manifest_path, cwd)
        undo_imports(manifest_path)


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
