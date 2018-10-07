import os
import sys

import requests

import conans
from conans import __version__ as client_version, tools
from conans.client.cmd.create import create
from conans.client.plugin_manager import PluginManager
from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.client_cache import ClientCache
from conans.client.conf import MIN_SERVER_COMPATIBLE_VERSION, ConanClientConfigParser
from conans.client.manager import ConanManager, existing_info_files
from conans.client.migrations import ClientMigrator
from conans.client.output import ConanOutput
from conans.client.profile_loader import read_profile, profile_from_args, \
    read_conaninfo_profile
from conans.client.recorder.search_recorder import SearchRecorder
from conans.client.recorder.upload_recoder import UploadRecorder
from conans.client.remote_manager import RemoteManager
from conans.client.remote_registry import RemoteRegistry
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClient
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.version_checker import VersionCheckerRequester
from conans.client.runner import ConanRunner
from conans.client.store.localdb import LocalDB
from conans.client.cmd.test import PackageTester
from conans.client.userio import UserIO
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.model.version import Version
from conans.paths import get_conan_user_home, CONANINFO, BUILD_INFO
from conans.util.env_reader import get_env
from conans.util.files import save_files, exception_message_safe, mkdir
from conans.util.log import configure_logger
from conans.util.tracer import log_command, log_exception
from conans.tools import set_global_instances
from conans.client.cmd.uploader import CmdUpload
from conans.client.cmd.profile import cmd_profile_update, cmd_profile_get,\
    cmd_profile_delete_key, cmd_profile_create, cmd_profile_list
from conans.client.cmd.search import Search
from conans.client.cmd.user import users_clean, users_list, user_set
from conans.client.importer import undo_imports
from conans.client.cmd.export import cmd_export, export_alias
from conans.unicode import get_cwd
from conans.client.remover import ConanRemover
from conans.client.cmd.download import download
from conans.model.workspace import Workspace
from conans.client.graph.graph_manager import GraphManager
from conans.client.loader import ConanFileLoader
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.graph.range_resolver import RangeResolver


default_manifest_folder = '.conan_manifests'


def get_request_timeout():
    timeout = os.getenv("CONAN_REQUEST_TIMEOUT")
    try:
        return float(timeout) if timeout is not None else None
    except ValueError:
        raise ConanException("Specify a numeric parameter for 'request_timeout'")


def get_basic_requester(client_cache):
    requester = requests.Session()
    # Manage the verify and the client certificates and setup proxies

    return ConanRequester(requester, client_cache, get_request_timeout())


def api_method(f):
    def wrapper(*args, **kwargs):
        the_self = args[0]
        try:
            curdir = get_cwd()
            log_command(f.__name__, kwargs)
            with tools.environment_append(the_self._client_cache.conan_config.env_vars):
                # Patch the globals in tools
                return f(*args, **kwargs)
        except Exception as exc:
            msg = exception_message_safe(exc)
            try:
                log_exception(exc, msg)
            except:
                pass
            raise
        finally:
            os.chdir(curdir)
    return wrapper


def _make_abs_path(path, cwd=None, default=None):
    """convert 'path' to absolute if necessary (could be already absolute)
    if not defined (empty, or None), will return 'default' one or 'cwd'
    """
    cwd = cwd or get_cwd()
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
    path = _make_abs_path(path, cwd)

    if os.path.isdir(path):  # Can be a folder
        if py:
            path = os.path.join(path, "conanfile.py")
        elif py is False:
            path = os.path.join(path, "conanfile.txt")
        else:
            path_py = os.path.join(path, "conanfile.py")
            if os.path.exists(path_py):
                path = path_py
            else:
                path = os.path.join(path, "conanfile.txt")

    if not os.path.isfile(path):  # Must exist
        raise ConanException("Conanfile not found: %s" % path)

    if py and not path.endswith(".py"):
        raise ConanException("A conanfile.py is needed (not valid conanfile.txt)")

    return path


class ConanAPIV1(object):

    @staticmethod
    def instance_remote_manager(requester, client_cache, user_io, _client_version,
                                min_server_compatible_version, plugin_manager):

        # Verify client version against remotes
        version_checker_req = VersionCheckerRequester(requester, _client_version,
                                                      min_server_compatible_version,
                                                      user_io.out)

        # To handle remote connections
        put_headers = client_cache.read_put_headers()
        rest_api_client = RestApiClient(user_io.out, requester=version_checker_req,
                                        put_headers=put_headers)
        # To store user and token
        localdb = LocalDB(client_cache.localdb)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_api_client, user_io, localdb)
        # Handle remote connections
        remote_manager = RemoteManager(client_cache, auth_manager, user_io.out, plugin_manager)
        return localdb, rest_api_client, remote_manager

    @staticmethod
    def factory(interactive=None):
        """Factory"""
        # Respect color env setting or check tty if unset
        color_set = "CONAN_COLOR_DISPLAY" in os.environ
        if ((color_set and get_env("CONAN_COLOR_DISPLAY", 1))
                or (not color_set
                    and hasattr(sys.stdout, "isatty")
                    and sys.stdout.isatty())):
            import colorama
            if get_env("PYCHARM_HOSTED"):  # in PyCharm disable convert/strip
                colorama.init(convert=False, strip=False)
            else:
                colorama.init()
            color = True
        else:
            color = False
        out = ConanOutput(sys.stdout, color)
        user_io = UserIO(out=out)

        try:
            user_home = get_conan_user_home()
            client_cache = migrate_and_get_client_cache(user_home, out)
            sys.path.append(os.path.join(user_home, "python"))
        except Exception as e:
            out.error(str(e))
            raise

        with tools.environment_append(client_cache.conan_config.env_vars):
            # Adjust CONAN_LOGGING_LEVEL with the env readed
            conans.util.log.logger = configure_logger()

            # Create Plugin Manager
            plugin_manager = PluginManager(client_cache.plugins_path,
                                           get_env("CONAN_PLUGINS", list()), user_io.out)

            # Get the new command instance after migrations have been done
            requester = get_basic_requester(client_cache)
            _, _, remote_manager = ConanAPIV1.instance_remote_manager(
                requester,
                client_cache, user_io,
                Version(client_version),
                Version(MIN_SERVER_COMPATIBLE_VERSION),
                plugin_manager)

            # Adjust global tool variables
            set_global_instances(out, requester)

            # Settings preprocessor
            if interactive is None:
                interactive = not get_env("CONAN_NON_INTERACTIVE", False)
            conan = ConanAPIV1(client_cache, user_io, get_conan_runner(), remote_manager,
                               plugin_manager, interactive=interactive)

        return conan, client_cache, user_io

    def __init__(self, client_cache, user_io, runner, remote_manager, plugin_manager,
                 interactive=True):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._remote_manager = remote_manager
        self._registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        if not interactive:
            self._user_io.disable_input()

        self._proxy = ConanProxy(client_cache, self._user_io.out, remote_manager, registry=self._registry)
        resolver = RangeResolver(self._user_io.out, client_cache, self._proxy)
        python_requires = ConanPythonRequire(self._proxy, resolver)
        self._loader = ConanFileLoader(self._runner, self._user_io.out, python_requires)
        self._graph_manager = GraphManager(self._user_io.out, self._client_cache, self._registry,
                                           self._remote_manager, self._loader, self._proxy, resolver)
        self._plugin_manager = plugin_manager

    def _init_manager(self, action_recorder):
        """Every api call gets a new recorder and new manager"""
        return ConanManager(self._client_cache, self._user_io, self._runner,
                            self._remote_manager, action_recorder, self._registry,
                            self._graph_manager, self._plugin_manager)

    @api_method
    def new(self, name, header=False, pure_c=False, test=False, exports_sources=False, bare=False,
            cwd=None, visual_versions=None, linux_gcc_versions=None, linux_clang_versions=None,
            osx_clang_versions=None, shared=None, upload_url=None, gitignore=None,
            gitlab_gcc_versions=None, gitlab_clang_versions=None,
            circleci_gcc_versions=None, circleci_clang_versions=None, circleci_osx_versions=None):
        from conans.client.cmd.new import cmd_new
        cwd = os.path.abspath(cwd or get_cwd())
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
                        circleci_osx_versions=circleci_osx_versions)

        save_files(cwd, files)
        for f in sorted(files):
            self._user_io.out.success("File saved: %s" % f)

    @api_method
    def test(self, path, reference, profile_name=None, settings=None, options=None, env=None,
             remote_name=None, update=False, build_modes=None, cwd=None, test_build_folder=None):

        settings = settings or []
        options = options or []
        env = env or []

        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        cwd = cwd or get_cwd()
        profile = profile_from_args(profile_name, settings, options, env, cwd,
                                    self._client_cache)
        reference = ConanFileReference.loads(reference)
        recorder = ActionRecorder()
        manager = self._init_manager(recorder)
        pt = PackageTester(manager, self._user_io)
        pt.install_build_and_test(conanfile_path, reference, profile, remote_name,
                                  update, build_modes=build_modes,
                                  test_build_folder=test_build_folder)

    @api_method
    def create(self, conanfile_path, name=None, version=None, user=None, channel=None,
               profile_name=None, settings=None,
               options=None, env=None, test_folder=None, not_export=False,
               build_modes=None,
               keep_source=False, keep_build=False, verify=None,
               manifests=None, manifests_interactive=None,
               remote_name=None, update=False, cwd=None, test_build_folder=None):
        """
        API method to create a conan package

        :param test_folder: default None   - looks for default 'test' or 'test_package' folder),
                                    string - test_folder path
                                    False  - disabling tests
        """
        settings = settings or []
        options = options or []
        env = env or []

        try:
            cwd = cwd or os.getcwd()
            recorder = ActionRecorder()
            conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)

            reference, conanfile = self._loader.load_export(conanfile_path, name, version, user, channel)

            # Make sure keep_source is set for keep_build
            keep_source = keep_source or keep_build
            # Forcing an export!
            if not not_export:
                cmd_export(conanfile_path, conanfile, reference, keep_source, self._user_io.out,
                           self._client_cache, self._plugin_manager)

            if build_modes is None:  # Not specified, force build the tested library
                build_modes = [conanfile.name]

            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
            manifest_folder, manifest_interactive, manifest_verify = manifests
            profile = profile_from_args(profile_name, settings, options, env,
                                        cwd, self._client_cache)

            manager = self._init_manager(recorder)
            recorder.add_recipe_being_developed(reference)

            create(reference, manager, self._user_io, profile, remote_name, update, build_modes,
                   manifest_folder, manifest_verify, manifest_interactive, keep_build,
                   test_build_folder, test_folder, conanfile_path)

            return recorder.get_info()

        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def export_pkg(self, conanfile_path, name, channel, source_folder=None, build_folder=None,
                   package_folder=None, install_folder=None, profile_name=None, settings=None,
                   options=None, env=None, force=False, user=None, version=None, cwd=None):

        settings = settings or []
        options = options or []
        env = env or []
        cwd = cwd or get_cwd()

        # Checks that info files exists if the install folder is specified
        if install_folder and not existing_info_files(_make_abs_path(install_folder, cwd)):
            raise ConanException("The specified install folder doesn't contain '%s' and '%s' "
                                 "files" % (CONANINFO, BUILD_INFO))

        conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)

        if package_folder:
            if build_folder or source_folder:
                raise ConanException("package folder definition incompatible with build and source folders")
            package_folder = _make_abs_path(package_folder, cwd)

        build_folder = _make_abs_path(build_folder, cwd)
        install_folder = _make_abs_path(install_folder, cwd, default=build_folder)
        source_folder = _make_abs_path(source_folder, cwd, default=os.path.dirname(conanfile_path))

        # Checks that no both settings and info files are specified
        if install_folder and existing_info_files(install_folder) and \
                (profile_name or settings or options or env):
            raise ConanException("%s and %s are found, at '%s' folder, so specifying profile, "
                                 "settings, options or env is not allowed" % (CONANINFO, BUILD_INFO,
                                                                              install_folder))

        infos_present = existing_info_files(install_folder)
        if not infos_present:
            profile = profile_from_args(profile_name, settings, options, env=env,
                                        cwd=cwd, client_cache=self._client_cache)
        else:
            profile = read_conaninfo_profile(install_folder)

        reference, conanfile = self._loader.load_export(conanfile_path, name, version, user, channel)
        cmd_export(conanfile_path, conanfile, reference, False, self._user_io.out,
                   self._client_cache, self._plugin_manager)

        recorder = ActionRecorder()
        manager = self._init_manager(recorder)
        manager.export_pkg(reference, source_folder=source_folder, build_folder=build_folder,
                           package_folder=package_folder, install_folder=install_folder,
                           profile=profile, force=force)

    @api_method
    def download(self, reference, remote_name=None, package=None, recipe=False):
        if package and recipe:
            raise ConanException("recipe parameter cannot be used together with package")
        # Install packages without settings (fixed ids or all)
        conan_ref = ConanFileReference.loads(reference)
        recorder = ActionRecorder()
        download(conan_ref, package, remote_name, recipe, self._registry, self._remote_manager,
                 self._client_cache, self._user_io.out, recorder, self._loader,
                 self._plugin_manager)

    @api_method
    def install_reference(self, reference, settings=None, options=None, env=None,
                          remote_name=None, verify=None, manifests=None,
                          manifests_interactive=None, build=None, profile_name=None,
                          update=False, generators=None, install_folder=None, cwd=None):

        try:
            recorder = ActionRecorder()
            cwd = cwd or os.getcwd()
            install_folder = _make_abs_path(install_folder, cwd)

            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
            manifest_folder, manifest_interactive, manifest_verify = manifests

            profile = profile_from_args(profile_name, settings, options, env, cwd,
                                        self._client_cache)

            if not generators:  # We don't want the default txt
                generators = False

            mkdir(install_folder)
            manager = self._init_manager(recorder)
            manager.install(reference=reference, install_folder=install_folder,
                            remote_name=remote_name, profile=profile, build_modes=build,
                            update=update, manifest_folder=manifest_folder,
                            manifest_verify=manifest_verify,
                            manifest_interactive=manifest_interactive,
                            generators=generators)
            return recorder.get_info()
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def install(self, path="", settings=None, options=None, env=None,
                remote_name=None, verify=None, manifests=None,
                manifests_interactive=None, build=None, profile_name=None,
                update=False, generators=None, no_imports=False, install_folder=None, cwd=None):

        try:
            recorder = ActionRecorder()
            cwd = cwd or os.getcwd()
            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
            manifest_folder, manifest_interactive, manifest_verify = manifests

            profile = profile_from_args(profile_name, settings, options, env, cwd,
                                        self._client_cache)

            wspath = _make_abs_path(path, cwd)
            if install_folder:
                if os.path.isabs(install_folder):
                    wsinstall_folder = install_folder
                else:
                    wsinstall_folder = os.path.join(cwd, install_folder)
            else:
                wsinstall_folder = None
            workspace = Workspace.get_workspace(wspath, wsinstall_folder)
            if workspace:
                self._user_io.out.success("Using conanws.yml file from %s" % workspace._base_folder)
                manager = self._init_manager(recorder)
                manager.install_workspace(profile, workspace, remote_name, build, update)
                return

            install_folder = _make_abs_path(install_folder, cwd)
            conanfile_path = _get_conanfile_path(path, cwd, py=None)
            manager = self._init_manager(recorder)
            manager.install(reference=conanfile_path,
                            install_folder=install_folder,
                            remote_name=remote_name,
                            profile=profile,
                            build_modes=build,
                            update=update,
                            manifest_folder=manifest_folder,
                            manifest_verify=manifest_verify,
                            manifest_interactive=manifest_interactive,
                            generators=generators,
                            no_imports=no_imports)
            return recorder.get_info()
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def config_get(self, item):
        config_parser = ConanClientConfigParser(self._client_cache.conan_conf_path)
        self._user_io.out.info(config_parser.get_item(item))
        return config_parser.get_item(item)

    @api_method
    def config_set(self, item, value):
        config_parser = ConanClientConfigParser(self._client_cache.conan_conf_path)
        config_parser.set_item(item, value)
        self._client_cache.invalidate()

    @api_method
    def config_rm(self, item):
        config_parser = ConanClientConfigParser(self._client_cache.conan_conf_path)
        config_parser.rm_item(item)
        self._client_cache.invalidate()

    @api_method
    def config_install(self, item, verify_ssl, config_type=None, args=None):
        # _make_abs_path, but could be not a path at all
        if item is not None and os.path.exists(item) and not os.path.isabs(item):
            item = os.path.abspath(item)

        from conans.client.conf.config_installer import configuration_install
        return configuration_install(item, self._client_cache, self._user_io.out, verify_ssl, config_type, args)

    def _info_get_profile(self, reference, install_folder, profile_name, settings, options, env):
        cwd = get_cwd()
        try:
            reference = ConanFileReference.loads(reference)
        except ConanException:
            reference = _get_conanfile_path(reference, cwd=None, py=None)
            if install_folder or not (profile_name or settings or options or env):
                # When not install folder is specified but neither any setting, we try to read the
                # info from cwd
                install_folder = _make_abs_path(install_folder, cwd)
                if existing_info_files(install_folder):
                    return reference, read_conaninfo_profile(install_folder)

        return reference, profile_from_args(profile_name, settings, options, env=env,
                                            cwd=cwd, client_cache=self._client_cache)

    @api_method
    def info_build_order(self, reference, settings=None, options=None, env=None,
                         profile_name=None, remote_name=None, build_order=None, check_updates=None,
                         install_folder=None):
        reference, profile = self._info_get_profile(reference, install_folder, profile_name, settings,
                                                    options, env)
        recorder = ActionRecorder()
        deps_graph, _, _ = self._graph_manager.load_graph(reference, None, profile, ["missing"], check_updates,
                                                          False, remote_name, recorder, workspace=None)
        return deps_graph.build_order(build_order)

    @api_method
    def info_nodes_to_build(self, reference, build_modes, settings=None, options=None, env=None,
                            profile_name=None, remote_name=None, check_updates=None, install_folder=None):
        reference, profile = self._info_get_profile(reference, install_folder, profile_name, settings,
                                                    options, env)
        recorder = ActionRecorder()
        deps_graph, conanfile, _ = self._graph_manager.load_graph(reference, None, profile, build_modes, check_updates,
                                                                  False, remote_name, recorder, workspace=None)
        nodes_to_build = deps_graph.nodes_to_build()
        return nodes_to_build, conanfile

    @api_method
    def info(self, reference, remote_name=None, settings=None, options=None, env=None,
             profile_name=None, update=False, install_folder=None, build=None):
        reference, profile = self._info_get_profile(reference, install_folder, profile_name, settings,
                                                    options, env)
        recorder = ActionRecorder()
        deps_graph, conanfile, _ = self._graph_manager.load_graph(reference, None, profile, build, update,
                                                                  False, remote_name, recorder, workspace=None)
        return deps_graph, conanfile

    @api_method
    def build(self, conanfile_path, source_folder=None, package_folder=None, build_folder=None,
              install_folder=None, should_configure=True, should_build=True, should_install=True,
              should_test=True, cwd=None):

        cwd = cwd or get_cwd()
        conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)
        build_folder = _make_abs_path(build_folder, cwd)
        install_folder = _make_abs_path(install_folder, cwd, default=build_folder)
        source_folder = _make_abs_path(source_folder, cwd, default=os.path.dirname(conanfile_path))
        default_pkg_folder = os.path.join(build_folder, "package")
        package_folder = _make_abs_path(package_folder, cwd, default=default_pkg_folder)

        recorder = ActionRecorder()
        manager = self._init_manager(recorder)
        manager.build(conanfile_path, source_folder, build_folder, package_folder,
                      install_folder, should_configure=should_configure, should_build=should_build,
                      should_install=should_install, should_test=should_test)

    @api_method
    def package(self, path, build_folder, package_folder, source_folder=None, install_folder=None, cwd=None):
        cwd = cwd or get_cwd()
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        build_folder = _make_abs_path(build_folder, cwd)
        install_folder = _make_abs_path(install_folder, cwd, default=build_folder)
        source_folder = _make_abs_path(source_folder, cwd, default=os.path.dirname(conanfile_path))
        default_pkg_folder = os.path.join(build_folder, "package")
        package_folder = _make_abs_path(package_folder, cwd, default=default_pkg_folder)

        recorder = ActionRecorder()
        manager = self._init_manager(recorder)
        manager.local_package(package_folder, conanfile_path, build_folder, source_folder,
                              install_folder)

    @api_method
    def source(self, path, source_folder=None, info_folder=None, cwd=None):
        cwd = cwd or get_cwd()
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        source_folder = _make_abs_path(source_folder, cwd)
        info_folder = _make_abs_path(info_folder, cwd)

        mkdir(source_folder)
        if not os.path.exists(info_folder):
            raise ConanException("Specified info-folder doesn't exist")

        recorder = ActionRecorder()
        manager = self._init_manager(recorder)
        manager.source(conanfile_path, source_folder, info_folder)

    @api_method
    def imports(self, path, dest=None, info_folder=None, cwd=None):
        """
        :param path: Path to the conanfile
        :param dest: Dir to put the imported files. (Abs path or relative to cwd)
        :param info_folder: Dir where the conaninfo.txt and conanbuildinfo.txt files are
        :param cwd: Current working directory
        :return: None
        """
        cwd = cwd or get_cwd()
        info_folder = _make_abs_path(info_folder, cwd)
        dest = _make_abs_path(dest, cwd)

        mkdir(dest)
        conanfile_abs_path = _get_conanfile_path(path, cwd, py=None)
        recorder = ActionRecorder()
        manager = self._init_manager(recorder)
        manager.imports(conanfile_abs_path, dest, info_folder)

    @api_method
    def imports_undo(self, manifest_path):
        cwd = get_cwd()
        manifest_path = _make_abs_path(manifest_path, cwd)
        undo_imports(manifest_path, self._user_io.out)

    @api_method
    def export(self, path, name, version, user, channel, keep_source=False, cwd=None):
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        reference, conanfile = self._loader.load_export(conanfile_path, name, version, user, channel)
        cmd_export(conanfile_path, conanfile, reference, keep_source, self._user_io.out,
                   self._client_cache, self._plugin_manager)

    @api_method
    def remove(self, pattern, query=None, packages=None, builds=None, src=False, force=False,
               remote_name=None, outdated=False):
        remover = ConanRemover(self._client_cache, self._remote_manager, self._user_io, self._registry)
        remover.remove(pattern, remote_name, src, builds, packages, force=force,
                       packages_query=query, outdated=outdated)

    @api_method
    def copy(self, reference, user_channel, force=False, packages=None):
        """
        param packages: None=No binaries, True=All binaries, else list of IDs
        """
        from conans.client.cmd.copy import cmd_copy
        # FIXME: conan copy does not support short-paths in Windows
        reference = ConanFileReference.loads(str(reference))
        cmd_copy(reference, user_channel, packages, self._client_cache,
                 self._user_io, self._remote_manager, self._registry, self._loader, force=force)

    @api_method
    def authenticate(self, name, password, remote_name):
        remote = self.get_remote_by_name(remote_name)
        _, remote_name, prev_user, user = self._remote_manager.authenticate(remote, name, password)
        return remote_name, prev_user, user

    @api_method
    def user_set(self, user, remote_name=None):
        remote = self.get_default_remote() if not remote_name else self.get_remote_by_name(remote_name)
        return user_set(self._client_cache.localdb, user, remote)

    @api_method
    def users_clean(self):
        users_clean(self._client_cache.localdb)

    @api_method
    def users_list(self, remote_name=None):
        info = {"error": False, "remotes": []}
        remotes = [self.get_remote_by_name(remote_name)] if remote_name else self.remote_list()
        try:
            info["remotes"] = users_list(self._client_cache.localdb, remotes)
            return info
        except ConanException as exc:
            info["error"] = True
            exc.info = info
            raise

    @api_method
    def search_recipes(self, pattern, remote_name=None, case_sensitive=False):
        recorder = SearchRecorder()
        search = Search(self._client_cache, self._remote_manager, self._registry)

        try:
            references = search.search_recipes(pattern, remote_name, case_sensitive)
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

        for remote_name, refs in references.items():
            for ref in refs:
                recorder.add_recipe(remote_name, ref, with_packages=False)
        return recorder.get_info()

    @api_method
    def search_packages(self, reference, query=None, remote_name=None, outdated=False):
        recorder = SearchRecorder()
        search = Search(self._client_cache, self._remote_manager, self._registry)

        try:
            reference = ConanFileReference.loads(str(reference))
            references = search.search_packages(reference, remote_name,
                                                query=query,
                                                outdated=outdated)
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

        for remote_name, remote_ref in references.items():
            recorder.add_recipe(remote_name, reference)
            if remote_ref.ordered_packages:
                for package_id, properties in remote_ref.ordered_packages.items():
                    package_recipe_hash = properties.get("recipe_hash", None)
                    recorder.add_package(remote_name, reference, package_id,
                                         properties.get("options", []),
                                         properties.get("settings", []),
                                         properties.get("full_requires", []),
                                         remote_ref.recipe_hash != package_recipe_hash)
        return recorder.get_info()

    @api_method
    def upload(self, pattern, package=None, remote_name=None, all_packages=False, confirm=False,
               retry=2, retry_wait=5, integrity_check=False, policy=None, query=None):
        """ Uploads a package recipe and the generated binary packages to a specified remote
        """

        recorder = UploadRecorder()
        uploader = CmdUpload(self._client_cache, self._user_io, self._remote_manager,
                             self._registry, self._loader, self._plugin_manager)
        try:
            uploader.upload(recorder, pattern, package, all_packages, confirm, retry,
                            retry_wait, integrity_check, policy, remote_name, query=query)
            return recorder.get_info()
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info()
            raise

    @api_method
    def remote_list(self):
        return self._registry.remotes

    @api_method
    def remote_add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        return self._registry.add(remote_name, url, verify_ssl, insert, force)

    @api_method
    def remote_remove(self, remote_name):
        return self._registry.remove(remote_name)

    @api_method
    def remote_update(self, remote_name, url, verify_ssl=True, insert=None):
        return self._registry.update(remote_name, url, verify_ssl, insert)

    @api_method
    def remote_rename(self, remote_name, new_new_remote):
        return self._registry.rename(remote_name, new_new_remote)

    @api_method
    def remote_list_ref(self):
        return self._registry.refs

    @api_method
    def remote_add_ref(self, reference, remote_name):
        reference = ConanFileReference.loads(str(reference))
        return self._registry.set_ref(reference, remote_name, check_exists=True)

    @api_method
    def remote_remove_ref(self, reference):
        reference = ConanFileReference.loads(str(reference))
        return self._registry.remove_ref(reference)

    @api_method
    def remote_update_ref(self, reference, remote_name):
        reference = ConanFileReference.loads(str(reference))
        return self._registry.update_ref(reference, remote_name)

    @api_method
    def profile_list(self):
        return cmd_profile_list(self._client_cache.profiles_path, self._user_io.out)

    @api_method
    def create_profile(self, profile_name, detect=False):
        return cmd_profile_create(profile_name, self._client_cache.profiles_path,
                                  self._user_io.out, detect)

    @api_method
    def update_profile(self, profile_name, key, value):
        return cmd_profile_update(profile_name, key, value, self._client_cache.profiles_path)

    @api_method
    def get_profile_key(self, profile_name, key):
        return cmd_profile_get(profile_name, key, self._client_cache.profiles_path)

    @api_method
    def delete_profile_key(self, profile_name, key):
        return cmd_profile_delete_key(profile_name, key, self._client_cache.profiles_path)

    @api_method
    def read_profile(self, profile=None):
        p, _ = read_profile(profile, get_cwd(), self._client_cache.profiles_path)
        return p

    @api_method
    def get_path(self, reference, package_id=None, path=None, remote_name=None):
        from conans.client.local_file_getter import get_path
        reference = ConanFileReference.loads(str(reference))
        if not path:
            path = "conanfile.py" if not package_id else "conaninfo.txt"

        if not remote_name:
            return get_path(self._client_cache, reference, package_id, path), path
        else:
            remote = self.get_remote_by_name(remote_name)
            return self._remote_manager.get_path(reference, package_id, path, remote), path

    @api_method
    def export_alias(self, reference, target_reference):
        reference = ConanFileReference.loads(reference)
        target_reference = ConanFileReference.loads(target_reference)
        return export_alias(reference, target_reference, self._client_cache)

    @api_method
    def get_default_remote(self):
        return self._registry.default_remote

    @api_method
    def get_remote_by_name(self, remote_name):
        return self._registry.remote(remote_name)


Conan = ConanAPIV1


def _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd):
    if manifests and manifests_interactive:
        raise ConanException("Do not specify both manifests and "
                             "manifests-interactive arguments")
    if verify and (manifests or manifests_interactive):
        raise ConanException("Do not specify both 'verify' and "
                             "'manifests' or 'manifests-interactive' arguments")
    manifest_folder = verify or manifests or manifests_interactive
    if manifest_folder:
        if not os.path.isabs(manifest_folder):
            if not cwd:
                raise ConanException("'cwd' should be defined if the manifest folder is relative.")
            manifest_folder = os.path.join(cwd, manifest_folder)
        manifest_verify = verify is not None
        manifest_interactive = manifests_interactive is not None
    else:
        manifest_verify = manifest_interactive = False

    return manifest_folder, manifest_interactive, manifest_verify


def get_conan_runner():
    print_commands_to_output = get_env("CONAN_PRINT_RUN_COMMANDS", False)
    generate_run_log_file = get_env("CONAN_LOG_RUN_TO_FILE", False)
    log_run_to_output = get_env("CONAN_LOG_RUN_TO_OUTPUT", True)
    runner = ConanRunner(print_commands_to_output, generate_run_log_file, log_run_to_output)
    return runner


def migrate_and_get_client_cache(base_folder, out, storage_folder=None):
    # Init paths
    client_cache = ClientCache(base_folder, storage_folder, out)

    # Migration system
    migrator = ClientMigrator(client_cache, Version(client_version), out)
    migrator.migrate()

    return client_cache
