import os

from collections import OrderedDict
from collections import namedtuple

from conans import __version__ as client_version
from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.cmd.build import cmd_build
from conans.client.cmd.create import create
from conans.client.cmd.download import download
from conans.client.cmd.export import cmd_export
from conans.client.cmd.test import install_build_and_test
from conans.client.cmd.uploader import CmdUpload
from conans.client.conf.required_version import check_required_conan_version
from conans.client.importer import run_imports, undo_imports
from conans.client.manager import deps_install
from conans.client.migrations import ClientMigrator
from conans.client.profile_loader import ProfileLoader
from conans.client.remover import ConanRemover
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
    def inspect(self, path, attributes, remote_name=None):
        app = ConanApp(self.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)])
        try:
            ref = RecipeReference.loads(path)
        except ConanException:
            conanfile_path = _get_conanfile_path(path, os.getcwd(), py=True)
            conanfile = app.loader.load_named(conanfile_path, None, None, None, None)
        else:
            if app.selected_remote:
                try:
                    if not ref.revision:
                        ref = app.remote_manager.get_latest_recipe_reference(ref, app.selected_remote)
                except NotFoundException:
                    raise RecipeNotFoundException(ref)
                else:
                    if not app.cache.exists_rrev(ref):
                        app.remote_manager.get_recipe(ref, app.selected_remote)

            result = app.proxy.get_recipe(ref)
            conanfile_path, _, _, ref = result
            conanfile = app.loader.load_basic(conanfile_path)
            conanfile.name = ref.name
            # FIXME: Conan 2.0, this should be a string, not a Version object
            conanfile.version = ref.version

        result = OrderedDict()
        if not attributes:
            attributes = ['name', 'version', 'url', 'homepage', 'license', 'author',
                          'description', 'topics', 'generators', 'exports', 'exports_sources',
                          'short_paths', 'build_policy', 'revision_mode', 'settings',
                          'options', 'default_options', 'deprecated']
        # TODO: Change this in Conan 2.0, cli stdout should display only fields with values,
        # json should contain all values for easy automation
        for attribute in attributes:
            try:
                attr = getattr(conanfile, attribute)
                if attribute == "options":
                    result[attribute] = attr.possible_values
                else:
                    result[attribute] = attr
            except AttributeError:
                result[attribute] = ''
        return result

    @api_method
    def test(self, path, reference, profile_names=None, settings=None, options=None, env=None,
             remote_name=None, update=False, build_modes=None, cwd=None, test_build_folder=None,
             lockfile=None, profile_build=None, conf=None):
        app = ConanApp(self.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)

        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        cwd = cwd or os.getcwd()
        lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
        profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                           profile_build, cwd,
                                                                           app.cache,
                                                                           lockfile=lockfile)
        ref = RecipeReference.loads(reference)
        install_build_and_test(app, conanfile_path, ref, profile_host,
                               profile_build, graph_lock, root_ref,
                               build_modes=build_modes, test_build_folder=test_build_folder)

    @api_method
    def create(self, conanfile_path, name=None, version=None, user=None, channel=None,
               profile_names=None, settings=None,
               options=None, env=None, test_folder=None,
               build_modes=None, remote_name=None, update=False, cwd=None, test_build_folder=None,
               lockfile=None, lockfile_out=None, ignore_dirty=False, profile_build=None,
               is_build_require=False, conf=None, require_overrides=None):
        """
        API method to create a conan package

        test_folder default None   - looks for default 'test' or 'test_package' folder),
                                    string - test_folder path
                                    False  - disabling tests
        """
        app = ConanApp(self.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)

        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        cwd = cwd or os.getcwd()

        try:
            conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               app.cache,
                                                                               lockfile=lockfile)
            new_ref = cmd_export(app, conanfile_path, name, version, user, channel,
                                 graph_lock=graph_lock,
                                 ignore_dirty=ignore_dirty)

            profile_host.options.scope(new_ref.name)

            if build_modes is None:  # Not specified, force build the tested library
                build_modes = [new_ref.name]

            # FIXME: Dirty hack: remove the root for the test_package/conanfile.py consumer
            root_ref = RecipeReference(None, None, None, None)
            create(app, new_ref, profile_host, profile_build,
                   graph_lock, root_ref, build_modes,
                   test_build_folder, test_folder, conanfile_path,
                   is_build_require=is_build_require, require_overrides=require_overrides)

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock.save(lockfile_out)
        except ConanException as exc:
            raise

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
            app.load_remotes([Remote(remote_name, None)])
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

    @api_method
    def remove(self, pattern, query=None, packages=None, builds=None, src=False, force=False,
               remote_name=None):
        app = ConanApp(self.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)])
        remover = ConanRemover(app)
        remover.remove(pattern, src, builds, packages, force=force,
                       packages_query=query)

    @api_method
    def upload(self, pattern, remote_name=None, all_packages=False, confirm=False,
               retry=None, retry_wait=None, integrity_check=False, policy=None, query=None,
               parallel_upload=False):
        """ Uploads a package recipe and the generated binary packages to a specified remote
        """
        app = ConanApp(self.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)])
        uploader = CmdUpload(app)
        uploader.upload(pattern, all_packages, confirm,
                        retry, retry_wait, integrity_check, policy, query=query,
                        parallel_upload=parallel_upload)

    @api_method
    def remove_system_reqs(self, reference):
        try:
            app = ConanApp(self.cache_folder)
            ref = RecipeReference.loads(reference)
            app.cache.get_pkg_layout(ref).remove_system_reqs()
            ConanOutput().info("Cache system_reqs from %s has been removed" % repr(ref))
        except Exception as error:
            raise ConanException("Unable to remove system_reqs: %s" % error)

    @api_method
    def remove_system_reqs_by_pattern(self, pattern):
        app = ConanApp(self.cache_folder)
        for ref in search_recipes(app.cache, pattern=pattern):
            self.remove_system_reqs(repr(ref))

    @api_method
    def get_path(self, reference, package_id=None, path=None, remote_name=None):
        app = ConanApp(self.cache_folder)
        def get_path(cache, ref, path, package_id):
            """ Return the contents for the given `path` inside current layout, it can
                be a single file or the list of files in a directory

                :param package_id: will retrieve the contents from the package directory
                :param path: path relative to the cache reference or package folder
            """
            assert not os.path.isabs(path)

            latest_rrev = cache.get_latest_recipe_reference(ref)

            if package_id is None:  # Get the file in the exported files
                folder = cache.ref_layout(latest_rrev).export()
            else:
                latest_pref = cache.get_latest_package_reference(PkgReference(latest_rrev, package_id))
                folder = cache.get_pkg_layout(latest_pref).package()

            abs_path = os.path.join(folder, path)

            if not os.path.exists(abs_path):
                raise NotFoundException("The specified path doesn't exist")

            if os.path.isdir(abs_path):
                return sorted([path_ for path_ in os.listdir(abs_path)
                               if not discarded_file(path)])
            else:
                return load(abs_path)

        ref = RecipeReference.loads(reference)
        if not path:
            path = "conanfile.py" if not package_id else "conaninfo.txt"

        if not remote_name:
            return get_path(app.cache, ref, path, package_id), path
        else:
            remote = app.cache.remotes_registry.read(remote_name)
            if not ref.revision:
                ref = app.remote_manager.get_latest_recipe_reference(ref, remote)
            if package_id:
                pref = PkgReference(ref, package_id)
                if not pref.revision:
                    pref = app.remote_manager.get_latest_package_reference(pref, remote)
                return app.remote_manager.get_package_file(pref, path, remote), path
            else:
                return app.remote_manager.get_recipe_file(ref, path, remote), path

    @api_method
    def editable_add(self, path, reference, cwd):
        app = ConanApp(self.cache_folder)
        # Retrieve conanfile.py from target_path
        target_path = _get_conanfile_path(path=path, cwd=cwd, py=True)

        # Check the conanfile is there, and name/version matches
        ref = RecipeReference.loads(reference)
        target_conanfile = app.loader.load_basic(target_path)
        if (target_conanfile.name and target_conanfile.name != ref.name) or \
                (target_conanfile.version and target_conanfile.version != ref.version):
            raise ConanException("Name and version from reference ({}) and target "
                                 "conanfile.py ({}/{}) must match".
                                 format(ref, target_conanfile.name, target_conanfile.version))

        app.cache.editable_packages.add(ref, target_path)

    @api_method
    def editable_remove(self, reference):
        app = ConanApp(self.cache_folder)
        # TODO: Validate the input reference
        ref = RecipeReference.loads(reference)
        return app.cache.editable_packages.remove(ref)

    @api_method
    def editable_list(self):
        app = ConanApp(self.cache_folder)
        return {str(k): v for k, v in app.cache.editable_packages.edited_refs.items()}


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
