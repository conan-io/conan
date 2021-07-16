import json
import os
import sys
from collections import OrderedDict
from collections import namedtuple
from io import StringIO

import conans
from conans import __version__ as client_version
from conans.client.cache.cache import ClientCache
from conans.client.cmd.build import cmd_build
from conans.client.cmd.create import create
from conans.client.cmd.download import download
from conans.client.cmd.export import cmd_export, export_alias
from conans.client.cmd.export_pkg import export_pkg
from conans.client.cmd.profile import (cmd_profile_create, cmd_profile_delete_key, cmd_profile_get,
                                       cmd_profile_list, cmd_profile_update)
from conans.client.cmd.test import install_build_and_test
from conans.client.cmd.uploader import CmdUpload
from conans.client.cmd.user import user_set, users_clean, users_list, token_present
from conans.client.conf.required_version import check_required_conan_version
from conans.client.generators import GeneratorManager
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.printer import print_graph
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import PyRequireLoader
from conans.client.graph.range_resolver import RangeResolver
from conans.client.hook_manager import HookManager
from conans.client.importer import run_imports, undo_imports
from conans.client.loader import ConanFileLoader
from conans.client.manager import deps_install
from conans.client.migrations import ClientMigrator
from conans.client.output import ConanOutput, colorama_initialize
from conans.client.profile_loader import profile_from_args, read_profile
from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.recorder.upload_recoder import UploadRecorder
from conans.client.remote_manager import RemoteManager
from conans.client.remover import ConanRemover
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.rest_client import RestApiClientFactory
from conans.client.runner import ConanRunner
from conans.client.source import config_source_local
from conans.client.tools.env import environment_append
from conans.client.userio import UserIO
from conans.errors import (ConanException, RecipeNotFoundException,
                           PackageNotFoundException, NotFoundException)
from conans.model.graph_lock import GraphLockFile, LOCKFILE, GraphLock
from conans.model.lock_bundle import LockBundle
from conans.model.manifest import discarded_file
from conans.model.ref import ConanFileReference, PackageReference, check_valid_ref
from conans.model.version import Version
from conans.paths import get_conan_user_home
from conans.search.search import search_recipes
from conans.tools import set_global_instances
from conans.util.conan_v2_mode import conan_v2_error
from conans.util.env_reader import get_env
from conans.util.files import exception_message_safe, mkdir, save_files, load, save
from conans.util.log import configure_logger
from conans.util.tracer import log_command, log_exception


class ProfileData(namedtuple("ProfileData", ["profiles", "settings", "options", "env", "conf"])):
    def __bool__(self):
        return bool(self.profiles or self.settings or self.options or self.env or self.conf)
    __nonzero__ = __bool__


def api_method(f):
    def wrapper(api, *args, **kwargs):
        quiet = kwargs.pop("quiet", False)
        try:  # getcwd can fail if Conan runs on an unexisting folder
            old_curdir = os.getcwd()
        except EnvironmentError:
            old_curdir = None
        old_output = api.user_io.out
        quiet_output = ConanOutput(StringIO(), color=api.color) if quiet else None
        try:
            api.create_app(quiet_output=quiet_output)
            log_command(f.__name__, kwargs)
            with environment_append(api.app.cache.config.env_vars):
                return f(api, *args, **kwargs)
        except Exception as exc:
            if quiet_output:
                old_output.write(quiet_output._stream.getvalue())
                old_output.flush()
            msg = exception_message_safe(exc)
            try:
                log_exception(exc, msg)
            except BaseException:
                pass
            raise
        finally:
            if old_curdir:
                os.chdir(old_curdir)
    return wrapper


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


class ConanApp(object):
    def __init__(self, cache_folder, user_io, http_requester=None, runner=None, quiet_output=None):
        # User IO, interaction and logging
        self.user_io = user_io
        self.out = self.user_io.out
        if quiet_output:
            self.user_io.out = quiet_output
            self.out = quiet_output

        self.cache_folder = cache_folder
        self.cache = ClientCache(self.cache_folder, self.out)
        self.config = self.cache.config
        if self.config.non_interactive or quiet_output:
            self.user_io.disable_input()

        # Adjust CONAN_LOGGING_LEVEL with the env readed
        conans.util.log.logger = configure_logger(self.config.logging_level,
                                                  self.config.logging_file)
        conans.util.log.logger.debug("INIT: Using config '%s'" % self.cache.conan_conf_path)

        self.hook_manager = HookManager(self.cache.hooks_path, self.config.hooks, self.out)
        # Wraps an http_requester to inject proxies, certs, etc
        self.requester = ConanRequester(self.config, http_requester)
        # To handle remote connections
        artifacts_properties = self.cache.read_artifacts_properties()
        rest_client_factory = RestApiClientFactory(self.out, self.requester, self.config,
                                                   artifacts_properties=artifacts_properties)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_client_factory, self.user_io, self.cache.localdb)
        # Handle remote connections
        self.remote_manager = RemoteManager(self.cache, auth_manager, self.out, self.hook_manager)

        # Adjust global tool variables
        set_global_instances(self.out, self.requester, self.config)

        self.runner = runner or ConanRunner(self.config.print_commands_to_output,
                                            self.config.generate_run_log_file,
                                            self.config.log_run_to_output,
                                            self.out)

        self.proxy = ConanProxy(self.cache, self.out, self.remote_manager)
        self.range_resolver = RangeResolver(self.cache, self.remote_manager)
        self.generator_manager = GeneratorManager()
        self.pyreq_loader = PyRequireLoader(self.proxy, self.range_resolver)
        self.loader = ConanFileLoader(self.runner, self.out,
                                      self.generator_manager, self.pyreq_loader, self.requester)
        self.binaries_analyzer = GraphBinariesAnalyzer(self.cache, self.out, self.remote_manager)
        self.graph_manager = GraphManager(self.out, self.cache, self.remote_manager, self.loader,
                                          self.proxy, self.range_resolver, self.binaries_analyzer)

    def load_remotes(self, remote_name=None, update=False, check_updates=False):
        remotes = self.cache.registry.load_remotes()
        if remote_name:
            remotes.select(remote_name)
        self.pyreq_loader.enable_remotes(update=update, check_updates=check_updates, remotes=remotes)
        return remotes


class ConanAPIV1(object):
    @classmethod
    def factory(cls):
        return cls(), None, None

    def __init__(self, cache_folder=None, output=None, user_io=None, http_requester=None,
                 runner=None):
        self.color = colorama_initialize()
        self.out = output or ConanOutput(sys.stdout, sys.stderr, self.color)
        self.user_io = user_io or UserIO(out=self.out)
        self.cache_folder = cache_folder or os.path.join(get_conan_user_home(), ".conan")
        self.http_requester = http_requester
        self.runner = runner
        self.app = None  # Api calls will create a new one every call
        # Migration system
        migrator = ClientMigrator(self.cache_folder, Version(client_version), self.out)
        migrator.migrate()
        check_required_conan_version(self.cache_folder, self.out)
        python_folder = os.path.join(self.cache_folder, "python")
        conan_v2_error("Using code from cache/python not allowed", os.path.isdir(python_folder))
        sys.path.append(python_folder)

    def create_app(self, quiet_output=None):
        self.app = ConanApp(self.cache_folder, self.user_io, self.http_requester,
                            self.runner, quiet_output=quiet_output)

    @api_method
    def new(self, name, header=False, pure_c=False, test=False, exports_sources=False, bare=False,
            cwd=None, visual_versions=None, linux_gcc_versions=None, linux_clang_versions=None,
            osx_clang_versions=None, shared=None, upload_url=None, gitignore=None,
            gitlab_gcc_versions=None, gitlab_clang_versions=None,
            circleci_gcc_versions=None, circleci_clang_versions=None, circleci_osx_versions=None,
            template=None, defines=None):
        from conans.client.cmd.new import cmd_new
        cwd = os.path.abspath(cwd or os.getcwd())
        files = cmd_new(name, header=header, pure_c=pure_c, test=test,
                        exports_sources=exports_sources, bare=bare,
                        visual_versions=visual_versions,
                        linux_gcc_versions=linux_gcc_versions,
                        linux_clang_versions=linux_clang_versions,
                        osx_clang_versions=osx_clang_versions, shared=shared,
                        upload_url=upload_url, gitignore=gitignore,
                        gitlab_gcc_versions=gitlab_gcc_versions,
                        gitlab_clang_versions=gitlab_clang_versions,
                        circleci_gcc_versions=circleci_gcc_versions,
                        circleci_clang_versions=circleci_clang_versions,
                        circleci_osx_versions=circleci_osx_versions,
                        template=template, cache=self.app.cache, defines=defines)

        save_files(cwd, files)
        for f in sorted(files):
            self.app.out.success("File saved: %s" % f)

    @api_method
    def inspect(self, path, attributes, remote_name=None):
        remotes = self.app.load_remotes(remote_name=remote_name)
        try:
            ref = ConanFileReference.loads(path)
        except ConanException:
            conanfile_path = _get_conanfile_path(path, os.getcwd(), py=True)
            conanfile = self.app.loader.load_named(conanfile_path, None, None, None, None)
        else:
            if remote_name:
                remotes = self.app.load_remotes()
                remote = remotes.get_remote(remote_name)
                try:  # get_recipe_manifest can fail, not in server
                    _, ref = self.app.remote_manager.get_recipe_manifest(ref, remote)
                except NotFoundException:
                    raise RecipeNotFoundException(ref)
                else:
                    ref = self.app.remote_manager.get_recipe(ref, remote)

            result = self.app.proxy.get_recipe(ref, False, False, remotes)
            conanfile_path, _, _, ref = result
            conanfile = self.app.loader.load_basic(conanfile_path)
            conanfile.name = ref.name
            # FIXME: Conan 2.0, this should be a string, not a Version object
            conanfile.version = ref.version

        result = OrderedDict()
        if not attributes:
            attributes = ['name', 'version', 'url', 'homepage', 'license', 'author',
                          'description', 'topics', 'generators', 'exports', 'exports_sources',
                          'short_paths', 'apply_env', 'build_policy', 'revision_mode', 'settings',
                          'options', 'default_options', 'deprecated']
        for attribute in attributes:
            try:
                attr = getattr(conanfile, attribute)
                result[attribute] = attr
            except AttributeError:
                result[attribute] = ''
        return result

    @api_method
    def test(self, path, reference, profile_names=None, settings=None, options=None, env=None,
             remote_name=None, update=False, build_modes=None, cwd=None, test_build_folder=None,
             lockfile=None, profile_build=None, conf=None):

        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)

        remotes = self.app.load_remotes(remote_name=remote_name, update=update)
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        cwd = cwd or os.getcwd()
        lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
        profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                           profile_build, cwd,
                                                                           self.app.cache,
                                                                           self.app.out,
                                                                           lockfile=lockfile)
        ref = ConanFileReference.loads(reference)
        recorder = ActionRecorder()
        install_build_and_test(self.app, conanfile_path, ref, profile_host,
                               profile_build, graph_lock, root_ref, remotes, update,
                               build_modes=build_modes, test_build_folder=test_build_folder,
                               recorder=recorder)

    @api_method
    def create(self, conanfile_path, name=None, version=None, user=None, channel=None,
               profile_names=None, settings=None,
               options=None, env=None, test_folder=None,
               build_modes=None, remote_name=None, update=False, cwd=None, test_build_folder=None,
               lockfile=None, lockfile_out=None, ignore_dirty=False, profile_build=None,
               is_build_require=False, conf=None):
        """
        API method to create a conan package

        test_folder default None   - looks for default 'test' or 'test_package' folder),
                                    string - test_folder path
                                    False  - disabling tests
        """

        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        cwd = cwd or os.getcwd()
        recorder = ActionRecorder()
        try:
            conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)

            remotes = self.app.load_remotes(remote_name=remote_name, update=update)
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               self.app.cache,
                                                                               self.app.out,
                                                                               lockfile=lockfile)

            new_ref = cmd_export(self.app, conanfile_path, name, version, user, channel,
                                 graph_lock=graph_lock,
                                 ignore_dirty=ignore_dirty)

            self.app.range_resolver.clear_output()  # invalidate version range output

            recorder.recipe_exported(new_ref)

            if build_modes is None:  # Not specified, force build the tested library
                build_modes = [new_ref.name]

            # FIXME: Dirty hack: remove the root for the test_package/conanfile.py consumer
            root_ref = ConanFileReference(None, None, None, None, validate=False)
            recorder.add_recipe_being_developed(new_ref)
            create(self.app, new_ref, profile_host, profile_build,
                   graph_lock, root_ref, remotes, update, build_modes,
                   test_build_folder, test_folder, conanfile_path, recorder=recorder,
                   is_build_require=is_build_require)

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
                graph_lock_file.save(lockfile_out)
            return recorder.get_info()

        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def export_pkg(self, conanfile_path, name, channel, source_folder=None, build_folder=None,
                   package_folder=None, profile_names=None, settings=None,
                   options=None, env=None, force=False, user=None, version=None, cwd=None,
                   lockfile=None, lockfile_out=None, ignore_dirty=False, profile_build=None,
                   conf=None):
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        remotes = self.app.load_remotes()
        cwd = cwd or os.getcwd()

        recorder = ActionRecorder()
        try:
            conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)

            if package_folder:
                if build_folder or source_folder:
                    raise ConanException("package folder definition incompatible with build "
                                         "and source folders")
                package_folder = _make_abs_path(package_folder, cwd)

            build_folder = _make_abs_path(build_folder, cwd)

            source_folder = _make_abs_path(source_folder, cwd,
                                           default=os.path.dirname(conanfile_path))

            for folder, path in {"source": source_folder, "build": build_folder,
                                 "package": package_folder}.items():
                if path and not os.path.exists(path):
                    raise ConanException("The {} folder '{}' does not exist."
                                         .format(folder, path))

            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            # Checks that no both settings and info files are specified
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               self.app.cache,
                                                                               self.app.out,
                                                                               lockfile=lockfile)

            new_ref = cmd_export(self.app, conanfile_path, name, version, user, channel,
                                 graph_lock=graph_lock, ignore_dirty=ignore_dirty)
            ref = new_ref.copy_clear_rev()
            # new_ref has revision
            recorder.recipe_exported(new_ref)
            recorder.add_recipe_being_developed(ref)
            export_pkg(self.app, recorder, new_ref, source_folder=source_folder,
                       build_folder=build_folder, package_folder=package_folder,
                       profile_host=profile_host, profile_build=profile_build,
                       graph_lock=graph_lock, root_ref=root_ref, force=force,
                       remotes=remotes)
            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
                graph_lock_file.save(lockfile_out)
            return recorder.get_info()
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def download(self, reference, remote_name=None, packages=None, recipe=False):
        if packages and recipe:
            raise ConanException("recipe parameter cannot be used together with packages")
        # Install packages without settings (fixed ids or all)
        if check_valid_ref(reference):
            ref = ConanFileReference.loads(reference)
            if packages and ref.revision is None:
                for package_id in packages:
                    if "#" in package_id:
                        raise ConanException("It is needed to specify the recipe revision if you "
                                             "specify a package revision")
            remotes = self.app.load_remotes(remote_name=remote_name)
            remote = remotes.get_remote(remote_name)
            recorder = ActionRecorder()
            download(self.app, ref, packages, remote, recipe, recorder, remotes=remotes)
        else:
            raise ConanException("Provide a valid full reference without wildcards.")

    @api_method
    def install_reference(self, reference, settings=None, options=None, env=None,
                          remote_name=None, build=None, profile_names=None,
                          update=False, generators=None, install_folder=None, cwd=None,
                          lockfile=None, lockfile_out=None, profile_build=None,
                          lockfile_node_id=None, is_build_require=False, conf=None):
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        recorder = ActionRecorder()
        cwd = cwd or os.getcwd()
        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               self.app.cache,
                                                                               self.app.out,
                                                                               lockfile=lockfile)

            install_folder = _make_abs_path(install_folder, cwd)

            mkdir(install_folder)
            remotes = self.app.load_remotes(remote_name=remote_name, update=update)
            deps_install(self.app, ref_or_path=reference, install_folder=install_folder, base_folder=cwd,
                         remotes=remotes, profile_host=profile_host, profile_build=profile_build,
                         graph_lock=graph_lock, root_ref=root_ref, build_modes=build,
                         update=update, generators=generators, recorder=recorder,
                         lockfile_node_id=lockfile_node_id,
                         is_build_require=is_build_require)

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
                graph_lock_file.save(lockfile_out)
            return recorder.get_info()
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def install(self, path="", name=None, version=None, user=None, channel=None,
                settings=None, options=None, env=None,
                remote_name=None, build=None, profile_names=None,
                update=False, generators=None, no_imports=False, install_folder=None, cwd=None,
                lockfile=None, lockfile_out=None, profile_build=None, conf=None):
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        recorder = ActionRecorder()
        cwd = cwd or os.getcwd()
        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               self.app.cache,
                                                                               self.app.out,
                                                                               name=name,
                                                                               version=version,
                                                                               user=user,
                                                                               channel=channel,
                                                                               lockfile=lockfile)

            install_folder = _make_abs_path(install_folder, cwd)
            conanfile_path = _get_conanfile_path(path, cwd, py=None)

            remotes = self.app.load_remotes(remote_name=remote_name, update=update)
            deps_install(app=self.app,
                         ref_or_path=conanfile_path,
                         install_folder=install_folder,
                         base_folder=cwd,
                         remotes=remotes,
                         profile_host=profile_host,
                         profile_build=profile_build,
                         graph_lock=graph_lock,
                         root_ref=root_ref,
                         build_modes=build,
                         update=update,
                         generators=generators,
                         no_imports=no_imports,
                         recorder=recorder)

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
                graph_lock_file.save(lockfile_out)
            return recorder.get_info()
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def config_get(self, item):
        if item == "storage.path":
            result = self.app.config.storage_path
        else:
            result = self.app.config.get_item(item)
        self.app.out.info(result)
        return result

    @api_method
    def config_set(self, item, value):
        self.app.config.set_item(item, value)

    @api_method
    def config_rm(self, item):
        self.app.config.rm_item(item)

    @api_method
    def config_install_list(self):
        if not os.path.isfile(self.app.cache.config_install_file):
            return []
        return json.loads(load(self.app.cache.config_install_file))

    @api_method
    def config_install_remove(self, index):
        if not os.path.isfile(self.app.cache.config_install_file):
            raise ConanException("There is no config data. Need to install config first.")
        configs = json.loads(load(self.app.cache.config_install_file))
        try:
            configs.pop(index)
        except Exception as e:
            raise ConanException("Config %s can't be removed: %s" % (index, str(e)))
        save(self.app.cache.config_install_file, json.dumps(configs))

    @api_method
    def config_install(self, path_or_url, verify_ssl, config_type=None, args=None,
                       source_folder=None, target_folder=None):
        from conans.client.conf.config_installer import configuration_install
        return configuration_install(self.app, path_or_url, verify_ssl,
                                     config_type=config_type, args=args,
                                     source_folder=source_folder, target_folder=target_folder)

    @api_method
    def config_home(self):
        return self.cache_folder

    @api_method
    def config_init(self, force=False):
        if force:
            self.app.cache.reset_config()
            self.app.cache.registry.reset_remotes()
            self.app.cache.reset_default_profile()
            self.app.cache.reset_settings()
        else:
            self.app.cache.initialize_config()
            self.app.cache.registry.initialize_remotes()
            self.app.cache.initialize_default_profile()
            self.app.cache.initialize_settings()

    def _info_args(self, reference_or_path, profile_host, profile_build,
                   name=None, version=None, user=None, channel=None, lockfile=None):
        cwd = os.getcwd()
        if check_valid_ref(reference_or_path):
            ref = ConanFileReference.loads(reference_or_path)
        else:
            ref = _get_conanfile_path(reference_or_path, cwd=None, py=None)

        lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
        profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host, profile_build,
                                                                           cwd,
                                                                           self.app.cache,
                                                                           self.app.out,
                                                                           name=name,
                                                                           version=version,
                                                                           user=user,
                                                                           channel=channel,
                                                                           lockfile=lockfile)

        return ref, profile_host, profile_build, graph_lock, root_ref

    @api_method
    def info_nodes_to_build(self, reference, build_modes, settings=None, options=None, env=None,
                            profile_names=None, remote_name=None, check_updates=None,
                            profile_build=None, name=None, version=None, user=None, channel=None,
                            conf=None):
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        reference, profile_host, profile_build, graph_lock, root_ref = \
            self._info_args(reference, profile_host, profile_build, name=name,
                            version=version, user=user, channel=channel)

        recorder = ActionRecorder()
        remotes = self.app.load_remotes(remote_name=remote_name, check_updates=check_updates)
        deps_graph = self.app.graph_manager.load_graph(reference, None, profile_host,
                                                       profile_build, graph_lock,
                                                       root_ref, build_modes, check_updates,
                                                       False, remotes, recorder)
        nodes_to_build = deps_graph.nodes_to_build()
        return nodes_to_build, deps_graph.root.conanfile

    @api_method
    def info(self, reference_or_path, remote_name=None, settings=None, options=None, env=None,
             profile_names=None, update=False, build=None, lockfile=None,
             profile_build=None, name=None, version=None, user=None, channel=None, conf=None):
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        reference, profile_host, profile_build, graph_lock, root_ref = \
            self._info_args(reference_or_path, profile_host,
                            profile_build, name=name, version=version,
                            user=user, channel=channel, lockfile=lockfile)
        recorder = ActionRecorder()
        # FIXME: Using update as check_update?
        remotes = self.app.load_remotes(remote_name=remote_name, check_updates=update)
        deps_graph = self.app.graph_manager.load_graph(reference, None, profile_host,
                                                       profile_build, graph_lock,
                                                       root_ref, build,
                                                       update, False, remotes, recorder)
        return deps_graph, deps_graph.root.conanfile

    @api_method
    def build(self, conanfile_path, name=None, version=None, user=None, channel=None,
              source_folder=None, package_folder=None, build_folder=None,
              install_folder=None, should_configure=True, should_build=True, should_install=True,
              should_test=True, cwd=None, settings=None, options=None, env=None,
              remote_name=None, build=None, profile_names=None,
              update=False, generators=None, no_imports=False,
              lockfile=None, lockfile_out=None, profile_build=None, conf=None):

        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        recorder = ActionRecorder()
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
                               self.app.cache, self.app.out,
                               name=name, version=version, user=user, channel=channel,
                               lockfile=lockfile)

            remotes = self.app.load_remotes(remote_name=remote_name, update=update)

            deps_info = deps_install(app=self.app,
                                     ref_or_path=conanfile_path,
                                     install_folder=install_folder,
                                     base_folder=cwd,
                                     remotes=remotes,
                                     profile_host=profile_host,
                                     profile_build=profile_build,
                                     graph_lock=graph_lock,
                                     root_ref=root_ref,
                                     build_modes=build,
                                     update=update,
                                     generators=generators,
                                     no_imports=no_imports,
                                     recorder=recorder)

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
                graph_lock_file.save(lockfile_out)

            conanfile = deps_info.root.conanfile
            cmd_build(self.app, conanfile_path, conanfile, base_path=cwd,
                      source_folder=source_folder, build_folder=build_folder,
                      package_folder=package_folder, install_folder=install_folder,
                      should_configure=should_configure, should_build=should_build,
                      should_install=should_install, should_test=should_test)

            return recorder.get_info()
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def source(self, path, source_folder=None, cwd=None):
        self.app.load_remotes()

        cwd = cwd or os.getcwd()
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        source_folder = _make_abs_path(source_folder, cwd)

        mkdir(source_folder)

        # only infos if exist
        conanfile = self.app.graph_manager.load_consumer_conanfile(conanfile_path)
        conanfile.folders.set_base_source(source_folder)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_package(None)

        config_source_local(conanfile, conanfile_path, self.app.hook_manager)

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
        cwd = cwd or os.getcwd()
        dest = _make_abs_path(dest, cwd)

        mkdir(dest)
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)
        conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=None)
        recorder = ActionRecorder()
        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = \
                get_graph_info(profile_host, profile_build, cwd,
                               self.app.cache, self.app.out, lockfile=lockfile)

            remotes = self.app.load_remotes(remote_name=None, update=False)
            deps_info = deps_install(app=self.app,
                                     ref_or_path=conanfile_path,
                                     install_folder=None,
                                     base_folder=cwd,
                                     profile_host=profile_host,
                                     profile_build=profile_build,
                                     graph_lock=graph_lock,
                                     root_ref=root_ref,
                                     recorder=recorder,
                                     remotes=remotes)
            conanfile = deps_info.root.conanfile
            conanfile.folders.set_base_imports(dest)
            return run_imports(conanfile)
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def imports_undo(self, manifest_path):
        cwd = os.getcwd()
        manifest_path = _make_abs_path(manifest_path, cwd)
        undo_imports(manifest_path, self.app.out)

    @api_method
    def export(self, path, name, version, user, channel, cwd=None,
               lockfile=None, lockfile_out=None, ignore_dirty=False):
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        graph_lock, graph_lock_file = None, None
        if lockfile:
            lockfile = _make_abs_path(lockfile, cwd)
            graph_lock_file = GraphLockFile.load(lockfile)
            graph_lock = graph_lock_file.graph_lock
            self.app.out.info("Using lockfile: '{}'".format(lockfile))

        self.app.load_remotes()
        cmd_export(self.app, conanfile_path, name, version, user, channel,
                   graph_lock=graph_lock, ignore_dirty=ignore_dirty)

        if lockfile_out and graph_lock_file:
            lockfile_out = _make_abs_path(lockfile_out, cwd)
            graph_lock_file.save(lockfile_out)

    @api_method
    def remove(self, pattern, query=None, packages=None, builds=None, src=False, force=False,
               remote_name=None):
        remotes = self.app.cache.registry.load_remotes()
        remover = ConanRemover(self.app.cache, self.app.remote_manager, self.app.user_io, remotes)
        remover.remove(pattern, remote_name, src, builds, packages, force=force,
                       packages_query=query)

    @api_method
    def authenticate(self, name, password, remote_name, skip_auth=False):
        # FIXME: 2.0 rename "name" to "user".
        # FIXME: 2.0 probably we should return also if we have been authenticated or not (skipped)
        # FIXME: 2.0 remove the skip_auth argument, that behavior will be done by:
        #      "conan user USERNAME -r remote" that will use the local credentials (
        #      and verify that are valid)
        #      against the server. Currently it only "associate" the USERNAME with the remote
        #      without checking anything else
        remote = self.get_remote_by_name(remote_name)

        if skip_auth and token_present(self.app.cache.localdb, remote, name):
            return remote.name, name, name
        if not password:
            name, password = self.app.user_io.request_login(remote_name=remote_name, username=name)

        remote_name, prev_user, user = self.app.remote_manager.authenticate(remote, name, password)
        return remote_name, prev_user, user

    @api_method
    def user_set(self, user, remote_name=None):
        remote = (self.get_default_remote() if not remote_name
                  else self.get_remote_by_name(remote_name))
        return user_set(self.app.cache.localdb, user, remote)

    @api_method
    def users_clean(self):
        users_clean(self.app.cache.localdb)

    @api_method
    def users_list(self, remote_name=None):
        info = {"error": False, "remotes": []}
        remotes = [self.get_remote_by_name(remote_name)] if remote_name else self.remote_list()
        try:
            info["remotes"] = users_list(self.app.cache.localdb, remotes)
            return info
        except ConanException as exc:
            info["error"] = True
            exc.info = info
            raise

    # @api_method
    # def search_packages(self, reference, query=None, remote_name=None):
    #     search_recorder = SearchRecorder()
    #     remotes = self.app.cache.registry.load_remotes()
    #     search = Search(self.app.cache, self.app.remote_manager, remotes)
    #
    #     try:
    #         ref = ConanFileReference.loads(reference)
    #         references = search.search_packages(ref, remote_name, query=query)
    #     except ConanException as exc:
    #         search_recorder.error = True
    #         exc.info = search_recorder.get_info()
    #         raise
    #
    #     for remote_name, remote_ref in references.items():
    #         search_recorder.add_recipe(remote_name, ref)
    #         if remote_ref.ordered_packages:
    #             for package_id, properties in remote_ref.ordered_packages.items():
    #                 # Artifactory uses field 'requires', conan_center 'full_requires'
    #                 requires = properties.get("requires", []) or properties.get("full_requires", [])
    #                 search_recorder.add_package(remote_name, ref,
    #                                             package_id, properties.get("options", []),
    #                                             properties.get("settings", []),
    #                                             requires)
    #     return search_recorder.get_info()

    @api_method
    def upload(self, pattern, package=None, remote_name=None, all_packages=False, confirm=False,
               retry=None, retry_wait=None, integrity_check=False, policy=None, query=None,
               parallel_upload=False):
        """ Uploads a package recipe and the generated binary packages to a specified remote
        """
        upload_recorder = UploadRecorder()
        uploader = CmdUpload(self.app.cache, self.app.user_io, self.app.remote_manager,
                             self.app.loader, self.app.hook_manager)
        remotes = self.app.load_remotes(remote_name=remote_name)
        try:
            uploader.upload(pattern, remotes, upload_recorder, package, all_packages, confirm,
                            retry, retry_wait, integrity_check, policy, query=query,
                            parallel_upload=parallel_upload)
            return upload_recorder.get_info()
        except ConanException as exc:
            upload_recorder.error = True
            exc.info = upload_recorder.get_info()
            raise

    @api_method
    def remote_list(self):
        return list(self.app.cache.registry.load_remotes().all_values())

    @api_method
    def remote_add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        return self.app.cache.registry.add(remote_name, url, verify_ssl, insert, force)

    @api_method
    def remote_remove(self, remote_name):
        return self.app.cache.registry.remove(remote_name)

    @api_method
    def remote_set_disabled_state(self, remote_name, state):
        return self.app.cache.registry.set_disabled_state(remote_name, state)

    @api_method
    def remote_update(self, remote_name, url, verify_ssl=True, insert=None):
        return self.app.cache.registry.update(remote_name, url, verify_ssl, insert)

    @api_method
    def remote_rename(self, remote_name, new_new_remote):
        return self.app.cache.registry.rename(remote_name, new_new_remote)

    @api_method
    def remote_list_ref(self, no_remote=False):
        result = {}
        for ref in self.app.cache.all_refs():
            result[ref] = self.app.cache.get_remote(ref)
        if no_remote:
            return {str(r): remote_name for r, remote_name in result.items() if not remote_name}
        else:
            return {str(r): remote_name for r, remote_name in result.items() if remote_name}

    @api_method
    def remote_add_ref(self, reference, remote_name):
        ref = ConanFileReference.loads(reference, validate=True)
        remote = self.app.cache.registry.load_remotes()[remote_name]
        all_rrevs = self.app.cache.get_recipe_revisions(ref)
        if len(all_rrevs) > 0:
            for rrev in all_rrevs:
                self.app.cache.set_remote(rrev, remote.name)
                for pkg in self.app.cache.get_package_ids(rrev):
                    for prev in self.app.cache.get_package_revisions(pkg):
                        self.app.cache.set_remote(prev, remote.name)
        else:
            raise ConanException(f"Can't set the remote for {str(ref)}. "
                                 f"It doesn't exist in the local cache")

    @api_method
    def remote_remove_ref(self, reference):
        ref = ConanFileReference.loads(reference, validate=True)
        for rrev in self.app.cache.get_recipe_revisions(ref):
            self.app.cache.set_remote(rrev, None)

    @api_method
    def remote_update_ref(self, reference, remote_name):
        ref = ConanFileReference.loads(reference, validate=True)
        remote = self.app.cache.registry.load_remotes()[remote_name]
        for rrev in self.app.cache.get_recipe_revisions(ref):
            self.app.cache.set_remote(rrev, remote.name)

    @api_method
    def remote_list_pref(self, reference, no_remote=False):
        ref = ConanFileReference.loads(reference, validate=True)
        result = {}
        for rrev in self.app.cache.get_recipe_revisions(ref):
            for pkg in self.app.cache.get_package_ids(rrev):
                for prev in self.app.cache.get_package_revisions(pkg):
                    result[prev] = self.app.cache.get_remote(prev)
        if no_remote:
            return {repr(prev): remote_name for prev, remote_name in result.items() if not remote_name}
        else:
            return {repr(prev): remote_name for prev, remote_name in result.items() if remote_name}

    @api_method
    def remote_add_pref(self, package_reference, remote_name):
        pref = PackageReference.loads(package_reference, validate=True)
        remote = self.app.cache.registry.load_remotes()[remote_name]
        # TODO: cache2.0 fix this, probably we have to ask to enter the ref with rrev?
        for rrev in self.app.cache.get_recipe_revisions(pref.ref):
            for pkg_id  in self.app.cache.get_package_ids(rrev):
                if pkg_id.id == pref.id:
                    for prev in self.app.cache.get_package_revisions(pkg_id):
                        if self.app.cache.get_remote(prev):
                            raise ConanException("%s already exists. Use update" % str(pref))
                        self.app.cache.set_remote(prev, remote.name)

    @api_method
    def remote_remove_pref(self, package_reference):
        pref = PackageReference.loads(package_reference, validate=True)
        for rrev in self.app.cache.get_recipe_revisions(pref.ref):
            for pkg_id in self.app.cache.get_package_ids(rrev):
                if pkg_id.id == pref.id:
                    for prev in self.app.cache.get_package_revisions(pkg_id):
                        if self.app.cache.get_remote(prev):
                            self.app.cache.set_remote(prev, None)

    @api_method
    def remote_update_pref(self, package_reference, remote_name):
        pref = PackageReference.loads(package_reference, validate=True)
        _ = self.app.cache.registry.load_remotes()[remote_name]
        for rrev in self.app.cache.get_recipe_revisions(pref.ref):
            for pkg_id in self.app.cache.get_package_ids(rrev):
                if pkg_id.id == pref.id:
                    for prev in self.app.cache.get_package_revisions(pkg_id):
                        if self.app.cache.get_remote(prev):
                            self.app.cache.set_remote(prev, remote_name)

    @api_method
    def remote_clean(self):
        return self.app.cache.registry.clear()

    @api_method
    def remove_system_reqs(self, reference):
        try:
            ref = ConanFileReference.loads(reference)
            self.app.cache.get_pkg_layout(ref).remove_system_reqs()
            self.app.out.info(
                "Cache system_reqs from %s has been removed" % repr(ref))
        except Exception as error:
            raise ConanException("Unable to remove system_reqs: %s" % error)

    @api_method
    def remove_system_reqs_by_pattern(self, pattern):
        for ref in search_recipes(self.app.cache, pattern=pattern):
            self.remove_system_reqs(repr(ref))

    @api_method
    def remove_locks(self):
        self.app.cache.remove_locks()

    @api_method
    def profile_list(self):
        return cmd_profile_list(self.app.cache.profiles_path, self.app.out)

    @api_method
    def create_profile(self, profile_name, detect=False, force=False):
        return cmd_profile_create(profile_name, self.app.cache.profiles_path,
                                  self.app.out, detect, force)

    @api_method
    def update_profile(self, profile_name, key, value):
        return cmd_profile_update(profile_name, key, value, self.app.cache.profiles_path)

    @api_method
    def get_profile_key(self, profile_name, key):
        return cmd_profile_get(profile_name, key, self.app.cache.profiles_path)

    @api_method
    def delete_profile_key(self, profile_name, key):
        return cmd_profile_delete_key(profile_name, key, self.app.cache.profiles_path)

    @api_method
    def read_profile(self, profile=None):
        p, _ = read_profile(profile, os.getcwd(), self.app.cache.profiles_path)
        return p

    @api_method
    def get_path(self, reference, package_id=None, path=None, remote_name=None):

        def get_path(cache, ref, path, package_id):
            """ Return the contents for the given `path` inside current layout, it can
                be a single file or the list of files in a directory

                :param package_id: will retrieve the contents from the package directory
                :param path: path relative to the cache reference or package folder
            """
            assert not os.path.isabs(path)

            latest_rrev = cache.get_latest_rrev(ref)

            if package_id is None:  # Get the file in the exported files
                folder = cache.ref_layout(latest_rrev).export()
            else:
                latest_pref = cache.get_latest_prev(PackageReference(latest_rrev, package_id))
                folder = cache.get_pkg_layout(latest_pref).package()

            abs_path = os.path.join(folder, path)

            if not os.path.exists(abs_path):
                raise NotFoundException("The specified path doesn't exist")

            if os.path.isdir(abs_path):
                # FIXME: 2.0: This env variable should not be declared here
                keep_python = get_env("CONAN_KEEP_PYTHON_FILES", False)
                return sorted([path_ for path_ in os.listdir(abs_path)
                               if not discarded_file(path, keep_python)])
            else:
                return load(abs_path)

        ref = ConanFileReference.loads(reference)
        if not path:
            path = "conanfile.py" if not package_id else "conaninfo.txt"

        if not remote_name:
            return get_path(self.app.cache, ref, path, package_id), path
        else:
            remote = self.get_remote_by_name(remote_name)
            if not ref.revision:
                ref = self.app.remote_manager.get_latest_recipe_revision(ref, remote)
            if package_id:
                pref = PackageReference(ref, package_id)
                if not pref.revision:
                    pref = self.app.remote_manager.get_latest_package_revision(pref, remote)
                return self.app.remote_manager.get_package_path(pref, path, remote), path
            else:
                return self.app.remote_manager.get_recipe_path(ref, path, remote), path

    @api_method
    def export_alias(self, reference, target_reference):
        self.app.load_remotes()

        ref = ConanFileReference.loads(reference)
        target_ref = ConanFileReference.loads(target_reference)

        if ref.name != target_ref.name:
            raise ConanException("An alias can only be defined to a package with the same name")

        # Do not allow to create an alias of a recipe that already has revisions
        # with that name
        latest_rrev = self.app.cache.get_latest_rrev(ref)
        if latest_rrev:
            alias_conanfile_path = self.app.cache.ref_layout(latest_rrev).conanfile()
            if os.path.exists(alias_conanfile_path):
                conanfile = self.app.loader.load_basic(alias_conanfile_path)
                if not getattr(conanfile, 'alias', None):
                    raise ConanException("Reference '{}' is already a package, remove it before "
                                         "creating and alias with the same name".format(ref))

        return export_alias(ref, target_ref, self.app.cache, output=self.app.out)

    @api_method
    def get_default_remote(self):
        return self.app.cache.registry.load_remotes().default

    @api_method
    def get_remote_by_name(self, remote_name):
        return self.app.cache.registry.load_remotes()[remote_name]

    @api_method
    def get_package_revisions(self, reference, remote_name=None):
        pref = PackageReference.loads(reference, validate=True)
        if not pref.ref.revision:
            raise ConanException("Specify a recipe reference with revision")
        if pref.revision:
            raise ConanException("Cannot list the revisions of a specific package revision")

        # TODO: cache2.0 we get the latest package revision for the recipe revision and package id
        pkg_revs = self.app.cache.get_package_revisions(pref, only_latest_prev=True)
        pkg_rev = pkg_revs[0] if pkg_revs else None
        if not remote_name:
            if not pkg_rev:
                raise PackageNotFoundException(pref)
            # Check the time in the associated remote if any
            remote_name = self.app.cache.get_remote(pkg_rev)
            remote = self.app.cache.registry.load_remotes()[remote_name] if remote_name else None
            rev_time = None
            if remote:
                try:
                    revisions = self.app.remote_manager.get_package_revisions(pref, remote)
                except RecipeNotFoundException:
                    pass
                except NotFoundException:
                    rev_time = None
                else:
                    tmp = {r["revision"]: r["time"] for r in revisions}
                    rev_time = tmp.get(pkg_rev.revision)

            return [{"revision": pkg_rev.revision, "time": rev_time}]
        else:
            remote = self.get_remote_by_name(remote_name)
            return self.app.remote_manager.get_package_revisions(pref, remote=remote)

    @api_method
    def editable_add(self, path, reference, cwd):
        # Retrieve conanfile.py from target_path
        target_path = _get_conanfile_path(path=path, cwd=cwd, py=True)

        self.app.load_remotes()

        # Check the conanfile is there, and name/version matches
        ref = ConanFileReference.loads(reference, validate=True)
        target_conanfile = self.app.loader.load_basic(target_path)
        if (target_conanfile.name and target_conanfile.name != ref.name) or \
                (target_conanfile.version and target_conanfile.version != ref.version):
            raise ConanException("Name and version from reference ({}) and target "
                                 "conanfile.py ({}/{}) must match".
                                 format(ref, target_conanfile.name, target_conanfile.version))

        self.app.cache.editable_packages.add(ref, target_path)

    @api_method
    def editable_remove(self, reference):
        ref = ConanFileReference.loads(reference, validate=True)
        return self.app.cache.editable_packages.remove(ref)

    @api_method
    def editable_list(self):
        return {str(k): v for k, v in self.app.cache.editable_packages.edited_refs.items()}

    @api_method
    def lock_update(self, old_lockfile, new_lockfile, cwd=None):
        cwd = cwd or os.getcwd()
        old_lockfile = _make_abs_path(old_lockfile, cwd)
        old_lock = GraphLockFile.load(old_lockfile)
        new_lockfile = _make_abs_path(new_lockfile, cwd)
        new_lock = GraphLockFile.load(new_lockfile)
        if old_lock.profile_host.dumps() != new_lock.profile_host.dumps():
            raise ConanException("Profiles of lockfiles are different\n%s:\n%s\n%s:\n%s"
                                 % (old_lockfile, old_lock.profile_host.dumps(),
                                    new_lockfile, new_lock.profile_host.dumps()))
        old_lock.graph_lock.update_lock(new_lock.graph_lock)
        old_lock.save(old_lockfile)

    @api_method
    def lock_build_order(self, lockfile, cwd=None):
        cwd = cwd or os.getcwd()
        lockfile = _make_abs_path(lockfile, cwd)

        graph_lock_file = GraphLockFile.load(lockfile)
        if graph_lock_file.profile_host is None:
            raise ConanException("Lockfiles with --base do not contain profile information, "
                                 "cannot be used. Create a full lockfile")

        graph_lock = graph_lock_file.graph_lock
        build_order = graph_lock.build_order()
        return build_order

    @api_method
    def lock_clean_modified(self, lockfile, cwd=None):
        cwd = cwd or os.getcwd()
        lockfile = _make_abs_path(lockfile, cwd)

        graph_lock_file = GraphLockFile.load(lockfile)
        graph_lock = graph_lock_file.graph_lock
        graph_lock.clean_modified()
        graph_lock_file.save(lockfile)

    @api_method
    def lock_install(self, lockfile, remote_name=None, build=None,
                     generators=None, install_folder=None, cwd=None,
                     lockfile_out=None, recipes=None):
        lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
        graph_info = get_graph_info(None, None, cwd,
                                    self.app.cache, self.app.out, lockfile=lockfile)
        phost, pbuild, graph_lock, root_ref = graph_info

        if not generators:  # We don't want the default txt
            generators = False

        install_folder = _make_abs_path(install_folder, cwd)

        mkdir(install_folder)
        remotes = self.app.load_remotes(remote_name=remote_name)
        recorder = ActionRecorder()
        root_id = graph_lock.root_node_id()
        reference = graph_lock.nodes[root_id].ref
        if recipes:
            graph = self.app.graph_manager.load_graph(reference, create_reference=None,
                                                      profile_host=phost, profile_build=pbuild,
                                                      graph_lock=graph_lock,
                                                      root_ref=root_ref,
                                                      build_mode=None,
                                                      check_updates=False, update=None,
                                                      remotes=remotes, recorder=recorder,
                                                      lockfile_node_id=root_id)
            print_graph(graph, self.app.out)
        else:
            deps_install(self.app, ref_or_path=reference, install_folder=install_folder,
                         base_folder=cwd,
                         profile_host=phost, profile_build=pbuild, graph_lock=graph_lock,
                         root_ref=root_ref, remotes=remotes, build_modes=build,
                         generators=generators, recorder=recorder, lockfile_node_id=root_id)

        if lockfile_out:
            lockfile_out = _make_abs_path(lockfile_out, cwd)
            graph_lock_file = GraphLockFile(phost, pbuild, graph_lock)
            graph_lock_file.save(lockfile_out)

    @api_method
    def lock_bundle_create(self, lockfiles, lockfile_out, cwd=None):
        cwd = cwd or os.getcwd()
        result = LockBundle.create(lockfiles, cwd)
        lockfile_out = _make_abs_path(lockfile_out, cwd)
        save(lockfile_out, result.dumps())

    @api_method
    def lock_bundle_build_order(self, lockfile, cwd=None):
        cwd = cwd or os.getcwd()
        lockfile = _make_abs_path(lockfile, cwd)
        lock_bundle = LockBundle()
        lock_bundle.loads(load(lockfile))
        build_order = lock_bundle.build_order()
        return build_order

    @api_method
    def lock_bundle_update(self, lock_bundle_path, cwd=None):
        cwd = cwd or os.getcwd()
        lock_bundle_path = _make_abs_path(lock_bundle_path, cwd)
        LockBundle.update_bundle(lock_bundle_path)

    @api_method
    def lock_bundle_clean_modified(self, lock_bundle_path, cwd=None):
        cwd = cwd or os.getcwd()
        lock_bundle_path = _make_abs_path(lock_bundle_path, cwd)
        LockBundle.clean_modified(lock_bundle_path)

    @api_method
    def lock_create(self, path, lockfile_out,
                    reference=None, name=None, version=None, user=None, channel=None,
                    profile_host=None, profile_build=None, remote_name=None, update=None, build=None,
                    base=None, lockfile=None):
        # profile_host is mandatory
        profile_host = profile_host or ProfileData(None, None, None, None, None)
        cwd = os.getcwd()

        if path and reference:
            raise ConanException("Both path and reference arguments were provided. Please provide "
                                 "only one of them")

        if path:
            ref_or_path = _make_abs_path(path, cwd)
            if os.path.isdir(ref_or_path):
                raise ConanException("Path argument must include filename "
                                     "like 'conanfile.py' or 'path/conanfile.py'")
            if not os.path.isfile(ref_or_path):
                raise ConanException("Conanfile does not exist in %s" % ref_or_path)
        else:  # reference
            ref_or_path = ConanFileReference.loads(reference)

        phost = pbuild = graph_lock = None
        if lockfile:
            lockfile = _make_abs_path(lockfile, cwd)
            graph_lock_file = GraphLockFile.load(lockfile)
            phost = graph_lock_file.profile_host
            pbuild = graph_lock_file.profile_build
            graph_lock = graph_lock_file.graph_lock
            graph_lock.relax()

        if not phost:
            phost = profile_from_args(profile_host.profiles, profile_host.settings,
                                      profile_host.options, profile_host.env, profile_host.conf,
                                      cwd, self.app.cache)

        if not pbuild:
            # Only work on the profile_build if something is provided
            pbuild = profile_from_args(profile_build.profiles, profile_build.settings,
                                       profile_build.options, profile_build.env, profile_build.conf,
                                       cwd, self.app.cache)

        root_ref = ConanFileReference(name, version, user, channel, validate=False)
        phost.process_settings(self.app.cache)
        if pbuild:
            pbuild.process_settings(self.app.cache)

        recorder = ActionRecorder()
        # FIXME: Using update as check_update?
        remotes = self.app.load_remotes(remote_name=remote_name, check_updates=update)
        deps_graph = self.app.graph_manager.load_graph(ref_or_path, None, phost,
                                                       pbuild, graph_lock, root_ref, build, update,
                                                       update, remotes, recorder)
        print_graph(deps_graph, self.app.out)

        # The computed graph-lock by the graph expansion
        graph_lock = graph_lock or GraphLock(deps_graph)
        # Pure graph_lock, no more graph_info mess
        graph_lock_file = GraphLockFile(phost, pbuild, graph_lock)
        if lockfile:
            new_graph_lock = GraphLock(deps_graph)
            graph_lock_file = GraphLockFile(phost, pbuild, new_graph_lock)
        if base:
            graph_lock_file.only_recipes()

        lockfile_out = _make_abs_path(lockfile_out or "conan.lock")
        graph_lock_file.save(lockfile_out)
        self.app.out.info("Generated lockfile: %s" % lockfile_out)


Conan = ConanAPIV1


def get_graph_info(profile_host, profile_build, cwd, cache, output,
                   name=None, version=None, user=None, channel=None, lockfile=None):

    root_ref = ConanFileReference(name, version, user, channel, validate=False)

    if lockfile:
        lockfile = lockfile if os.path.isfile(lockfile) else os.path.join(lockfile, LOCKFILE)
        graph_lock_file = GraphLockFile.load(lockfile)
        profile_host = graph_lock_file.profile_host
        profile_build = graph_lock_file.profile_build
        if profile_host is None:
            raise ConanException("Lockfiles with --base do not contain profile information, "
                                 "cannot be used. Create a full lockfile")
        profile_host.process_settings(cache, preprocess=False)
        profile_build.process_settings(cache, preprocess=False)
        graph_lock = graph_lock_file.graph_lock
        output.info("Using lockfile: '{}'".format(lockfile))
        return profile_host, profile_build, graph_lock, root_ref

    phost = profile_from_args(profile_host.profiles, profile_host.settings,
                              profile_host.options, profile_host.env, profile_host.conf,
                              cwd, cache)
    phost.process_settings(cache)
    # Only work on the profile_build if something is provided
    pbuild = profile_from_args(profile_build.profiles, profile_build.settings,
                               profile_build.options, profile_build.env, profile_build.conf,
                               cwd, cache)
    pbuild.process_settings(cache)

    # Preprocess settings and convert to real settings
    # Apply the new_config to the profiles the global one, so recipes get it too
    # TODO: This means lockfiles contain whole copy of the config here?
    # FIXME: Apply to locked graph-info as well
    phost.conf.rebase_conf_definition(cache.new_config)
    pbuild.conf.rebase_conf_definition(cache.new_config)
    return phost, pbuild, None, root_ref
