import os
import sys
from collections import OrderedDict

import requests

import conans
from conans import __version__ as client_version
from conans.client import packager, tools
from conans.client.cache.cache import ClientCache
from conans.client.cmd.build import build
from conans.client.cmd.create import create
from conans.client.cmd.download import download
from conans.client.cmd.export import cmd_export, export_alias, export_recipe, export_source, \
    check_casing_conflict
from conans.client.cmd.export_pkg import export_pkg
from conans.client.cmd.profile import (cmd_profile_create, cmd_profile_delete_key, cmd_profile_get,
                                       cmd_profile_list, cmd_profile_update)
from conans.client.cmd.search import Search
from conans.client.cmd.test import PackageTester
from conans.client.cmd.uploader import CmdUpload
from conans.client.cmd.user import user_set, users_clean, users_list
from conans.client.conf import ConanClientConfigParser
from conans.client.graph.graph import RECIPE_EDITABLE
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.printer import print_graph
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.graph.range_resolver import RangeResolver
from conans.client.hook_manager import HookManager
from conans.client.importer import run_imports, undo_imports
from conans.client.installer import BinaryInstaller
from conans.client.loader import ConanFileLoader
from conans.client.manager import ConanManager
from conans.client.migrations import ClientMigrator
from conans.client.output import ConanOutput
from conans.client.profile_loader import profile_from_args, read_profile
from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.recorder.search_recorder import SearchRecorder
from conans.client.recorder.upload_recoder import UploadRecorder
from conans.client.remote_manager import RemoteManager
from conans.client.remover import ConanRemover
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.rest_client import RestApiClient
from conans.client.runner import ConanRunner
from conans.client.source import config_source_local
from conans.client.store.localdb import LocalDB
from conans.client.userio import UserIO
from conans.errors import (ConanException, RecipeNotFoundException, ConanMigrationError,
                           PackageNotFoundException, NoRestV2Available, NotFoundException)
from conans.model.conan_file import get_env_context_manager
from conans.model.editable_layout import get_editable_abs_path
from conans.model.graph_info import GraphInfo, GRAPH_INFO_FILE
from conans.model.ref import ConanFileReference, PackageReference, check_valid_ref
from conans.model.version import Version
from conans.model.workspace import Workspace
from conans.paths import BUILD_INFO, CONANINFO, get_conan_user_home
from conans.tools import set_global_instances
from conans.unicode import get_cwd
from conans.util.env_reader import get_env
from conans.util.files import exception_message_safe, mkdir, save_files
from conans.util.log import configure_logger
from conans.util.tracer import log_command, log_exception

default_manifest_folder = '.conan_manifests'


def get_request_timeout():
    timeout = os.getenv("CONAN_REQUEST_TIMEOUT")
    try:
        return float(timeout) if timeout is not None else None
    except ValueError:
        raise ConanException("Specify a numeric parameter for 'request_timeout'")


def get_basic_requester(cache):
    requester = requests.Session()
    # Manage the verify and the client certificates and setup proxies

    return ConanRequester(requester, cache, get_request_timeout())


def api_method(f):
    def wrapper(*args, **kwargs):
        the_self = args[0]
        the_self.invalidate_caches()
        try:
            curdir = get_cwd()
            log_command(f.__name__, kwargs)
            with tools.environment_append(the_self._cache.config.env_vars):
                # Patch the globals in tools
                return f(*args, **kwargs)
        except Exception as exc:
            msg = exception_message_safe(exc)
            try:
                log_exception(exc, msg)
            except BaseException:
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

    @staticmethod
    def instance_remote_manager(requester, cache, user_io, hook_manager):

        # To handle remote connections
        put_headers = cache.read_put_headers()
        rest_api_client = RestApiClient(user_io.out, requester,
                                        revisions_enabled=cache.config.revisions_enabled,
                                        put_headers=put_headers)
        # To store user and token
        localdb = LocalDB.create(cache.localdb)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_api_client, user_io, localdb)
        # Handle remote connections
        remote_manager = RemoteManager(cache, auth_manager, user_io.out, hook_manager)
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
            cache = migrate_and_get_cache(user_home, out)
            sys.path.append(os.path.join(user_home, "python"))
        except Exception as e:
            out.error(str(e))
            raise ConanMigrationError(e)

        with tools.environment_append(cache.config.env_vars):
            # Adjust CONAN_LOGGING_LEVEL with the env readed
            conans.util.log.logger = configure_logger()
            conans.util.log.logger.debug("INIT: Using config '%s'" % cache.conan_conf_path)

            # Create Hook Manager
            hook_manager = HookManager(cache.hooks_path, get_env("CONAN_HOOKS", list()),
                                       user_io.out)

            # Get the new command instance after migrations have been done
            requester = get_basic_requester(cache)
            _, _, remote_manager = ConanAPIV1.instance_remote_manager(requester, cache, user_io,
                                                                      hook_manager)

            # Adjust global tool variables
            set_global_instances(out, requester)

            # Settings preprocessor
            if interactive is None:
                interactive = not get_env("CONAN_NON_INTERACTIVE", False)
            conan = ConanAPIV1(cache, user_io, get_conan_runner(), remote_manager,
                               hook_manager, requester, interactive=interactive)

        return conan, cache, user_io

    def __init__(self, cache, user_io, runner, remote_manager, hook_manager, requester,
                 interactive=True):
        assert isinstance(user_io, UserIO)
        assert isinstance(cache, ClientCache)
        self._cache = cache
        self._user_io = user_io
        self._runner = runner
        self._remote_manager = remote_manager
        self._requester = requester
        if not interactive:
            self._user_io.disable_input()

        self._proxy = ConanProxy(cache, self._user_io.out, remote_manager)
        resolver = RangeResolver(cache, self._proxy)
        self.python_requires = ConanPythonRequire(self._proxy, resolver)
        self._loader = ConanFileLoader(self._runner, self._user_io.out, self.python_requires)

        self._graph_manager = GraphManager(self._user_io.out, self._cache,
                                           self._remote_manager, self._loader, self._proxy,
                                           resolver)
        self._hook_manager = hook_manager

    def invalidate_caches(self):
        self._loader.invalidate_caches()
        self._cache.invalidate()

    def _init_manager(self, action_recorder):
        """Every api call gets a new recorder and new manager"""
        return ConanManager(self._cache, self._user_io,
                            self._remote_manager, action_recorder,
                            self._graph_manager, self._hook_manager)

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
    def inspect(self, path, attributes, remote_name=None):
        try:
            ref = ConanFileReference.loads(path)
        except ConanException:
            conanfile_path = _get_conanfile_path(path, get_cwd(), py=True)
            ref = os.path.basename(conanfile_path)
            conanfile_class = self._loader.load_class(conanfile_path)
        else:
            update = True if remote_name else False
            result = self._proxy.get_recipe(ref, update, update, remote_name, ActionRecorder())
            conanfile_path, _, _, ref = result
            conanfile_class = self._loader.load_class(conanfile_path)
            conanfile_class.name = ref.name
            conanfile_class.version = ref.version
        conanfile = conanfile_class(self._user_io.out, None, str(ref))

        result = OrderedDict()
        if not attributes:
            attributes = ['name', 'version', 'url', 'homepage', 'license', 'author',
                          'description', 'topics', 'generators', 'exports', 'exports_sources',
                          'short_paths', 'apply_env', 'build_policy', 'revision_mode', 'settings',
                          'options', 'default_options']
        for attribute in attributes:
            try:
                attr = getattr(conanfile, attribute)
                result[attribute] = attr
            except AttributeError as e:
                raise ConanException(str(e))
        return result

    @api_method
    def test(self, path, reference, profile_names=None, settings=None, options=None, env=None,
             remote_name=None, update=False, build_modes=None, cwd=None, test_build_folder=None):

        settings = settings or []
        options = options or []
        env = env or []

        self.python_requires.enable_remotes(update=update, remote_name=remote_name)

        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        cwd = cwd or get_cwd()
        graph_info = get_graph_info(profile_names, settings, options, env, cwd, None,
                                    self._cache, self._user_io.out)
        ref = ConanFileReference.loads(reference)
        recorder = ActionRecorder()
        manager = self._init_manager(recorder)
        pt = PackageTester(manager, self._user_io)
        pt.install_build_and_test(conanfile_path, ref, graph_info, remote_name,
                                  update, build_modes=build_modes,
                                  test_build_folder=test_build_folder)

    @api_method
    def create(self, conanfile_path, name=None, version=None, user=None, channel=None,
               profile_names=None, settings=None,
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

            self.python_requires.enable_remotes(update=update, remote_name=remote_name)

            conanfile = self._loader.load_export(conanfile_path, name, version, user, channel)
            ref = ConanFileReference(conanfile.name, conanfile.version, conanfile.user,
                                     conanfile.channel)
            # Make sure keep_source is set for keep_build
            keep_source = keep_source or keep_build
            # Forcing an export!
            if not not_export:
                check_casing_conflict(cache=self._cache, ref=ref)
                package_layout = self._cache.package_layout(ref, short_paths=conanfile.short_paths)
                new_ref = cmd_export(package_layout, conanfile_path, conanfile, keep_source,
                                     self._cache.config.revisions_enabled, self._user_io.out,
                                     self._hook_manager)
                # The new_ref contains the revision
                recorder.recipe_exported(new_ref)

            if build_modes is None:  # Not specified, force build the tested library
                build_modes = [conanfile.name]

            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
            manifest_folder, manifest_interactive, manifest_verify = manifests
            graph_info = get_graph_info(profile_names, settings, options, env, cwd, None,
                                        self._cache, self._user_io.out)

            manager = self._init_manager(recorder)
            recorder.add_recipe_being_developed(ref)

            create(ref, manager, self._user_io, graph_info, remote_name, update, build_modes,
                   manifest_folder, manifest_verify, manifest_interactive, keep_build,
                   test_build_folder, test_folder, conanfile_path)

            return recorder.get_info(self._cache.config.revisions_enabled)

        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info(self._cache.config.revisions_enabled)
            raise

    @api_method
    def export_pkg(self, conanfile_path, name, channel, source_folder=None, build_folder=None,
                   package_folder=None, install_folder=None, profile_names=None, settings=None,
                   options=None, env=None, force=False, user=None, version=None, cwd=None):

        settings = settings or []
        options = options or []
        env = env or []
        cwd = cwd or get_cwd()

        try:
            recorder = ActionRecorder()
            conanfile_path = _get_conanfile_path(conanfile_path, cwd, py=True)

            if package_folder:
                if build_folder or source_folder:
                    raise ConanException("package folder definition incompatible with build "
                                         "and source folders")
                package_folder = _make_abs_path(package_folder, cwd)

            build_folder = _make_abs_path(build_folder, cwd)
            if install_folder:
                install_folder = _make_abs_path(install_folder, cwd)
            else:
                # FIXME: This is a hack for old UI, need to be fixed in Conan 2.0
                if os.path.exists(os.path.join(build_folder, GRAPH_INFO_FILE)):
                    install_folder = build_folder
            source_folder = _make_abs_path(source_folder, cwd,
                                           default=os.path.dirname(conanfile_path))

            # Checks that no both settings and info files are specified
            graph_info = get_graph_info(profile_names, settings, options, env, cwd, install_folder,
                                        self._cache, self._user_io.out)

            conanfile = self._loader.load_export(conanfile_path, name, version, user, channel)
            ref = ConanFileReference(conanfile.name, conanfile.version, user, channel)

            check_casing_conflict(cache=self._cache, ref=ref)
            package_layout = self._cache.package_layout(ref, short_paths=conanfile.short_paths)
            new_ref = cmd_export(package_layout, conanfile_path, conanfile, False,
                                 self._cache.config.revisions_enabled, self._user_io.out,
                                 self._hook_manager)
            # new_ref has revision
            recorder.recipe_exported(new_ref)
            recorder.add_recipe_being_developed(ref)

            export_pkg(self._cache, self._graph_manager, self._hook_manager, recorder,
                       self._user_io.out,
                       ref, source_folder=source_folder, build_folder=build_folder,
                       package_folder=package_folder, install_folder=install_folder,
                       graph_info=graph_info, force=force)
            return recorder.get_info(self._cache.config.revisions_enabled)
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info(self._cache.config.revisions_enabled)
            raise

    @api_method
    def download(self, reference, remote_name=None, package=None, recipe=False):
        # FIXME: The "package" parameter name is very bad, it is a list of package_ids
        if package and recipe:
            raise ConanException("recipe parameter cannot be used together with package")
        # Install packages without settings (fixed ids or all)
        ref = ConanFileReference.loads(reference)

        if check_valid_ref(ref, allow_pattern=False):
            if package and ref.revision is None:
                for package_id in package:
                    if "#" in package_id:
                        raise ConanException("It is needed to specify the recipe revision if you "
                                             "specify a package revision")
            recorder = ActionRecorder()
            download(ref, package, remote_name, recipe, self._remote_manager,
                     self._cache, self._user_io.out, recorder, self._loader,
                     self._hook_manager)
        else:
            raise ConanException("Provide a valid full reference without wildcards.")

    @api_method
    def workspace_install(self, path, settings=None, options=None, env=None,
                          remote_name=None, build=None, profile_name=None,
                          update=False, cwd=None):
        cwd = cwd or get_cwd()
        abs_path = os.path.normpath(os.path.join(cwd, path))

        self.python_requires.enable_remotes(update=update, remote_name=remote_name)

        workspace = Workspace(abs_path, self._cache)
        graph_info = get_graph_info(profile_name, settings, options, env, cwd, None,
                                    self._cache, self._user_io.out)

        self._user_io.out.info("Configuration:")
        self._user_io.out.writeln(graph_info.profile.dumps())

        self._cache.editable_packages.override(workspace.get_editable_dict())

        recorder = ActionRecorder()
        deps_graph, _ = self._graph_manager.load_graph(workspace.root, None, graph_info, build,
                                                       False, update, remote_name, recorder)

        print_graph(deps_graph, self._user_io.out)

        # Inject the generators before installing
        for node in deps_graph.nodes:
            if node.recipe == RECIPE_EDITABLE:
                generators = workspace[node.ref].generators
                if generators is not None:
                    tmp = list(node.conanfile.generators)
                    tmp.extend([g for g in generators if g not in tmp])
                    node.conanfile.generators = tmp

        installer = BinaryInstaller(self._cache, self._user_io.out, self._remote_manager,
                                    recorder=recorder, hook_manager=self._hook_manager)
        installer.install(deps_graph, keep_build=False, graph_info=graph_info)
        workspace.generate(cwd, deps_graph, self._user_io.out)

    @api_method
    def install_reference(self, reference, settings=None, options=None, env=None,
                          remote_name=None, verify=None, manifests=None,
                          manifests_interactive=None, build=None, profile_names=None,
                          update=False, generators=None, install_folder=None, cwd=None):

        try:
            recorder = ActionRecorder()
            cwd = cwd or os.getcwd()
            install_folder = _make_abs_path(install_folder, cwd)

            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
            manifest_folder, manifest_interactive, manifest_verify = manifests

            graph_info = get_graph_info(profile_names, settings, options, env, cwd, None,
                                        self._cache, self._user_io.out)

            if not generators:  # We don't want the default txt
                generators = False

            mkdir(install_folder)
            self.python_requires.enable_remotes(update=update, remote_name=remote_name)
            manager = self._init_manager(recorder)
            manager.install(ref_or_path=reference, install_folder=install_folder,
                            remote_name=remote_name, graph_info=graph_info, build_modes=build,
                            update=update, manifest_folder=manifest_folder,
                            manifest_verify=manifest_verify,
                            manifest_interactive=manifest_interactive,
                            generators=generators)
            return recorder.get_info(self._cache.config.revisions_enabled)
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info(self._cache.config.revisions_enabled)
            raise

    @api_method
    def install(self, path="", name=None, version=None, user=None, channel=None,
                settings=None, options=None, env=None,
                remote_name=None, verify=None, manifests=None,
                manifests_interactive=None, build=None, profile_names=None,
                update=False, generators=None, no_imports=False, install_folder=None, cwd=None):

        try:
            recorder = ActionRecorder()
            cwd = cwd or os.getcwd()
            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
            manifest_folder, manifest_interactive, manifest_verify = manifests

            graph_info = get_graph_info(profile_names, settings, options, env, cwd, None,
                                        self._cache, self._user_io.out,
                                        name=name, version=version, user=user, channel=channel)

            install_folder = _make_abs_path(install_folder, cwd)
            conanfile_path = _get_conanfile_path(path, cwd, py=None)
            self.python_requires.enable_remotes(update=update, remote_name=remote_name)
            manager = self._init_manager(recorder)
            manager.install(ref_or_path=conanfile_path,
                            install_folder=install_folder,
                            remote_name=remote_name,
                            graph_info=graph_info,
                            build_modes=build,
                            update=update,
                            manifest_folder=manifest_folder,
                            manifest_verify=manifest_verify,
                            manifest_interactive=manifest_interactive,
                            generators=generators,
                            no_imports=no_imports)
            return recorder.get_info(self._cache.config.revisions_enabled)
        except ConanException as exc:
            recorder.error = True
            exc.info = recorder.get_info(self._cache.config.revisions_enabled)
            raise

    @api_method
    def config_get(self, item):
        config_parser = ConanClientConfigParser(self._cache.conan_conf_path)
        self._user_io.out.info(config_parser.get_item(item))
        return config_parser.get_item(item)

    @api_method
    def config_set(self, item, value):
        config_parser = ConanClientConfigParser(self._cache.conan_conf_path)
        config_parser.set_item(item, value)
        self._cache.invalidate()

    @api_method
    def config_rm(self, item):
        config_parser = ConanClientConfigParser(self._cache.conan_conf_path)
        config_parser.rm_item(item)
        self._cache.invalidate()

    @api_method
    def config_install(self, path_or_url, verify_ssl, config_type=None, args=None,
                       source_folder=None, target_folder=None):
        from conans.client.conf.config_installer import configuration_install
        return configuration_install(path_or_url, self._cache, self._user_io.out, verify_ssl,
                                     requester=self._requester, config_type=config_type, args=args,
                                     source_folder=source_folder, target_folder=target_folder)

    def _info_args(self, reference_or_path, install_folder, profile_names, settings, options, env):
        cwd = get_cwd()
        try:
            ref = ConanFileReference.loads(reference_or_path)
            install_folder = None
        except ConanException:
            ref = _get_conanfile_path(reference_or_path, cwd=None, py=None)

            if install_folder:
                install_folder = _make_abs_path(install_folder, cwd)
            else:
                # FIXME: This is a hack for old UI, need to be fixed in Conan 2.0
                if os.path.exists(os.path.join(cwd, GRAPH_INFO_FILE)):
                    install_folder = cwd

        graph_info = get_graph_info(profile_names, settings, options, env, cwd, install_folder,
                                    self._cache, self._user_io.out)

        return ref, graph_info

    @api_method
    def info_build_order(self, reference, settings=None, options=None, env=None,
                         profile_names=None, remote_name=None, build_order=None, check_updates=None,
                         install_folder=None):
        reference, graph_info = self._info_args(reference, install_folder, profile_names,
                                                settings, options, env)
        recorder = ActionRecorder()
        self.python_requires.enable_remotes(check_updates=check_updates, remote_name=remote_name)
        deps_graph, _ = self._graph_manager.load_graph(reference, None, graph_info, ["missing"],
                                                       check_updates, False, remote_name,
                                                       recorder)
        return deps_graph.build_order(build_order)

    @api_method
    def info_nodes_to_build(self, reference, build_modes, settings=None, options=None, env=None,
                            profile_names=None, remote_name=None, check_updates=None,
                            install_folder=None):
        reference, graph_info = self._info_args(reference, install_folder, profile_names,
                                                settings, options, env)
        recorder = ActionRecorder()
        self.python_requires.enable_remotes(check_updates=check_updates, remote_name=remote_name)
        deps_graph, conanfile = self._graph_manager.load_graph(reference, None, graph_info,
                                                               build_modes, check_updates,
                                                               False, remote_name, recorder)
        nodes_to_build = deps_graph.nodes_to_build()
        return nodes_to_build, conanfile

    @api_method
    def info(self, reference, remote_name=None, settings=None, options=None, env=None,
             profile_names=None, update=False, install_folder=None, build=None):
        reference, graph_info = self._info_args(reference, install_folder, profile_names,
                                                settings, options, env)
        recorder = ActionRecorder()
        # FIXME: Using update as check_update?
        self.python_requires.enable_remotes(check_updates=update, remote_name=remote_name)
        deps_graph, conanfile = self._graph_manager.load_graph(reference, None, graph_info, build,
                                                               update, False, remote_name,
                                                               recorder)
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

        build(self._graph_manager, self._hook_manager, conanfile_path,
              source_folder, build_folder, package_folder, install_folder,
              should_configure=should_configure, should_build=should_build,
              should_install=should_install, should_test=should_test)

    @api_method
    def package(self, path, build_folder, package_folder, source_folder=None, install_folder=None,
                cwd=None):
        cwd = cwd or get_cwd()
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        build_folder = _make_abs_path(build_folder, cwd)
        install_folder = _make_abs_path(install_folder, cwd, default=build_folder)
        source_folder = _make_abs_path(source_folder, cwd, default=os.path.dirname(conanfile_path))
        default_pkg_folder = os.path.join(build_folder, "package")
        package_folder = _make_abs_path(package_folder, cwd, default=default_pkg_folder)

        if package_folder == build_folder:
            raise ConanException("Cannot 'conan package' to the build folder. "
                                 "--build-folder and package folder can't be the same")
        conanfile = self._graph_manager.load_consumer_conanfile(conanfile_path, install_folder,
                                                                deps_info_required=True)
        with get_env_context_manager(conanfile):
            packager.create_package(conanfile, None, source_folder, build_folder, package_folder,
                                    install_folder, self._hook_manager, conanfile_path, None,
                                    local=True, copy_info=True)

    @api_method
    def source(self, path, source_folder=None, info_folder=None, cwd=None):
        cwd = cwd or get_cwd()
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        source_folder = _make_abs_path(source_folder, cwd)
        info_folder = _make_abs_path(info_folder, cwd)

        mkdir(source_folder)
        if not os.path.exists(info_folder):
            raise ConanException("Specified info-folder doesn't exist")

        # only infos if exist
        conanfile = self._graph_manager.load_consumer_conanfile(conanfile_path, info_folder)
        conanfile_folder = os.path.dirname(conanfile_path)
        if conanfile_folder != source_folder:
            conanfile.output.info("Executing exports to: %s" % source_folder)
            export_recipe(conanfile, conanfile_folder, source_folder)
            export_source(conanfile, conanfile_folder, source_folder)
        config_source_local(source_folder, conanfile, conanfile_path, self._hook_manager)

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
        conanfile = self._graph_manager.load_consumer_conanfile(conanfile_abs_path, info_folder,
                                                                deps_info_required=True)
        run_imports(conanfile, dest)

    @api_method
    def imports_undo(self, manifest_path):
        cwd = get_cwd()
        manifest_path = _make_abs_path(manifest_path, cwd)
        undo_imports(manifest_path, self._user_io.out)

    @api_method
    def export(self, path, name, version, user, channel, keep_source=False, cwd=None):
        conanfile_path = _get_conanfile_path(path, cwd, py=True)
        conanfile = self._loader.load_export(conanfile_path, name, version, user, channel)
        ref = ConanFileReference(conanfile.name, conanfile.version, conanfile.user,
                                 conanfile.channel)
        check_casing_conflict(cache=self._cache, ref=ref)
        package_layout = self._cache.package_layout(ref, short_paths=conanfile.short_paths)
        cmd_export(package_layout, conanfile_path, conanfile, keep_source,
                   self._cache.config.revisions_enabled, self._user_io.out,
                   self._hook_manager)

    @api_method
    def remove(self, pattern, query=None, packages=None, builds=None, src=False, force=False,
               remote_name=None, outdated=False):
        remover = ConanRemover(self._cache, self._remote_manager, self._user_io)
        remover.remove(pattern, remote_name, src, builds, packages, force=force,
                       packages_query=query, outdated=outdated)

    @api_method
    def copy(self, reference, user_channel, force=False, packages=None):
        """
        param packages: None=No binaries, True=All binaries, else list of IDs
        """
        from conans.client.cmd.copy import cmd_copy
        # FIXME: conan copy does not support short-paths in Windows
        ref = ConanFileReference.loads(reference)
        cmd_copy(ref, user_channel, packages, self._cache,
                 self._user_io, self._remote_manager, self._loader, force=force)

    @api_method
    def authenticate(self, name, password, remote_name):
        remote = self.get_remote_by_name(remote_name)
        _, remote_name, prev_user, user = self._remote_manager.authenticate(remote, name, password)
        return remote_name, prev_user, user

    @api_method
    def user_set(self, user, remote_name=None):
        remote = (self.get_default_remote() if not remote_name
                  else self.get_remote_by_name(remote_name))
        return user_set(self._cache.localdb, user, remote)

    @api_method
    def users_clean(self):
        users_clean(self._cache.localdb)

    @api_method
    def users_list(self, remote_name=None):
        info = {"error": False, "remotes": []}
        remotes = [self.get_remote_by_name(remote_name)] if remote_name else self.remote_list()
        try:
            info["remotes"] = users_list(self._cache.localdb, remotes)
            return info
        except ConanException as exc:
            info["error"] = True
            exc.info = info
            raise

    @api_method
    def search_recipes(self, pattern, remote_name=None, case_sensitive=False):
        search_recorder = SearchRecorder()
        search = Search(self._cache, self._remote_manager)

        try:
            references = search.search_recipes(pattern, remote_name, case_sensitive)
        except ConanException as exc:
            search_recorder.error = True
            exc.info = search_recorder.get_info()
            raise

        for remote_name, refs in references.items():
            for ref in refs:
                search_recorder.add_recipe(remote_name, ref, with_packages=False)
        return search_recorder.get_info()

    @api_method
    def search_packages(self, reference, query=None, remote_name=None, outdated=False):
        search_recorder = SearchRecorder()
        search = Search(self._cache, self._remote_manager)

        try:
            ref = ConanFileReference.loads(reference)
            references = search.search_packages(ref, remote_name, query=query, outdated=outdated)
        except ConanException as exc:
            search_recorder.error = True
            exc.info = search_recorder.get_info()
            raise

        for remote_name, remote_ref in references.items():
            search_recorder.add_recipe(remote_name, ref)
            if remote_ref.ordered_packages:
                for package_id, properties in remote_ref.ordered_packages.items():
                    package_recipe_hash = properties.get("recipe_hash", None)
                    search_recorder.add_package(remote_name, ref,
                                                package_id, properties.get("options", []),
                                                properties.get("settings", []),
                                                properties.get("full_requires", []),
                                                remote_ref.recipe_hash != package_recipe_hash)
        return search_recorder.get_info()

    @api_method
    def upload(self, pattern, package=None, remote_name=None, all_packages=False, confirm=False,
               retry=2, retry_wait=5, integrity_check=False, policy=None, query=None):
        """ Uploads a package recipe and the generated binary packages to a specified remote
        """

        upload_recorder = UploadRecorder()
        uploader = CmdUpload(self._cache, self._user_io, self._remote_manager,
                             self._loader, self._hook_manager)
        try:
            uploader.upload(upload_recorder, pattern, package, all_packages, confirm, retry,
                            retry_wait, integrity_check, policy, remote_name, query=query)
            return upload_recorder.get_info()
        except ConanException as exc:
            upload_recorder.error = True
            exc.info = upload_recorder.get_info()
            raise

    @api_method
    def remote_list(self):
        return self._cache.registry.remotes.list

    @api_method
    def remote_add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        return self._cache.registry.remotes.add(remote_name, url, verify_ssl, insert, force)

    @api_method
    def remote_remove(self, remote_name):
        return self._cache.registry.remotes.remove(remote_name)

    @api_method
    def remote_update(self, remote_name, url, verify_ssl=True, insert=None):
        return self._cache.registry.remotes.update(remote_name, url, verify_ssl, insert)

    @api_method
    def remote_rename(self, remote_name, new_new_remote):
        return self._cache.registry.remotes.rename(remote_name, new_new_remote)

    @api_method
    def remote_list_ref(self):
        return {r: remote_name for r, remote_name in self._cache.registry.refs.list.items()}

    @api_method
    def remote_add_ref(self, reference, remote_name):
        ref = ConanFileReference.loads(reference, validate=True)
        return self._cache.registry.refs.set(ref, remote_name, check_exists=True)

    @api_method
    def remote_remove_ref(self, reference):
        ref = ConanFileReference.loads(reference, validate=True)
        return self._cache.registry.refs.remove(ref)

    @api_method
    def remote_update_ref(self, reference, remote_name):
        ref = ConanFileReference.loads(reference, validate=True)
        return self._cache.registry.refs.update(ref, remote_name)

    @api_method
    def remote_list_pref(self, reference):
        ref = ConanFileReference.loads(reference, validate=True)
        ret = {}
        tmp = self._cache.registry.prefs.list
        for package_reference, remote in tmp.items():
            pref = PackageReference.loads(package_reference)
            if pref.ref == ref:
                ret[pref.full_repr()] = remote
        return ret

    @api_method
    def remote_add_pref(self, package_reference, remote_name):
        pref = PackageReference.loads(package_reference, validate=True)
        return self._cache.registry.prefs.set(pref, remote_name, check_exists=True)

    @api_method
    def remote_remove_pref(self, package_reference):
        pref = PackageReference.loads(package_reference, validate=True)
        return self._cache.registry.prefs.remove(pref)

    @api_method
    def remote_update_pref(self, package_reference, remote_name):
        pref = PackageReference.loads(package_reference, validate=True)
        return self._cache.registry.prefs.update(pref, remote_name)

    def remote_clean(self):
        return self._cache.registry.remotes.clean()

    @api_method
    def profile_list(self):
        return cmd_profile_list(self._cache.profiles_path, self._user_io.out)

    @api_method
    def create_profile(self, profile_name, detect=False):
        return cmd_profile_create(profile_name, self._cache.profiles_path,
                                  self._user_io.out, detect)

    @api_method
    def update_profile(self, profile_name, key, value):
        return cmd_profile_update(profile_name, key, value, self._cache.profiles_path)

    @api_method
    def get_profile_key(self, profile_name, key):
        return cmd_profile_get(profile_name, key, self._cache.profiles_path)

    @api_method
    def delete_profile_key(self, profile_name, key):
        return cmd_profile_delete_key(profile_name, key, self._cache.profiles_path)

    @api_method
    def read_profile(self, profile=None):
        p, _ = read_profile(profile, get_cwd(), self._cache.profiles_path)
        return p

    @api_method
    def get_path(self, reference, package_id=None, path=None, remote_name=None):
        ref = ConanFileReference.loads(reference)
        if not path:
            path = "conanfile.py" if not package_id else "conaninfo.txt"

        if not remote_name:
            package_layout = self._cache.package_layout(ref, short_paths=None)
            return package_layout.get_path(path=path, package_id=package_id), path
        else:
            remote = self.get_remote_by_name(remote_name)
            if self._cache.config.revisions_enabled and not ref.revision:
                ref = self._remote_manager.get_latest_recipe_revision(ref, remote)
            if package_id:
                pref = PackageReference(ref, package_id)
                if self._cache.config.revisions_enabled and not pref.revision:
                    pref = self._remote_manager.get_latest_package_revision(pref, remote)
                return self._remote_manager.get_package_path(pref, path, remote), path
            else:
                return self._remote_manager.get_recipe_path(ref, path, remote), path

    @api_method
    def export_alias(self, reference, target_reference):
        ref = ConanFileReference.loads(reference)
        target_ref = ConanFileReference.loads(target_reference)

        if ref.name != target_ref.name:
            raise ConanException("An alias can only be defined to a package with the same name")

        # Do not allow to override an existing package
        alias_conanfile_path = self._cache.package_layout(ref).conanfile()
        if os.path.exists(alias_conanfile_path):
            conanfile_class = self._loader.load_class(alias_conanfile_path)
            conanfile = conanfile_class(self._user_io.out, None, str(ref))
            if not getattr(conanfile, 'alias', None):
                raise ConanException("Reference '{}' is already a package, remove it before creating"
                                     " and alias with the same name".format(ref))

        package_layout = self._cache.package_layout(ref)
        return export_alias(package_layout, target_ref,
                            revisions_enabled=self._cache.config.revisions_enabled,
                            output=self._user_io.out)

    @api_method
    def get_default_remote(self):
        return self._cache.registry.remotes.default

    @api_method
    def get_remote_by_name(self, remote_name):
        return self._cache.registry.remotes.get(remote_name)

    @api_method
    def get_recipe_revisions(self, reference, remote_name=None):
        ref = ConanFileReference.loads(str(reference))
        if ref.revision:
            raise ConanException("Cannot list the revisions of a specific recipe revision")

        if not remote_name:
            layout = self._cache.package_layout(ref)
            try:
                rev = layout.recipe_revision()
            except RecipeNotFoundException as e:
                e.print_rev = True
                raise e

            # Check the time in the associated remote if any
            remote = self._cache.registry.refs.get(ref)
            rev_time = None
            if remote:
                try:
                    revisions = self._remote_manager.get_recipe_revisions(ref, remote)
                except RecipeNotFoundException:
                    pass
                except (NoRestV2Available, NotFoundException):
                    rev_time = None
                else:
                    tmp = {r["revision"]: r["time"] for r in revisions}
                    rev_time = tmp.get(rev)

            return [{"revision": rev, "time": rev_time}]
        else:
            remote = self.get_remote_by_name(remote_name)
            return self._remote_manager.get_recipe_revisions(ref, remote=remote)

    @api_method
    def get_package_revisions(self, reference, remote_name=None):
        pref = PackageReference.loads(str(reference), validate=True)
        if not pref.ref.revision:
            raise ConanException("Specify a recipe reference with revision")
        if pref.revision:
            raise ConanException("Cannot list the revisions of a specific package revision")

        if not remote_name:
            layout = self._cache.package_layout(pref.ref)
            try:
                rev = layout.package_revision(pref)
            except (RecipeNotFoundException, PackageNotFoundException) as e:
                e.print_rev = True
                raise e

            # Check the time in the associated remote if any
            remote = self._cache.registry.refs.get(pref.ref)
            rev_time = None
            if remote:
                try:
                    revisions = self._remote_manager.get_package_revisions(pref, remote)
                except RecipeNotFoundException:
                    pass
                except (NoRestV2Available, NotFoundException):
                    rev_time = None
                else:
                    tmp = {r["revision"]: r["time"] for r in revisions}
                    rev_time = tmp.get(rev)

            return [{"revision": rev, "time": rev_time}]
        else:
            remote = self.get_remote_by_name(remote_name)
            return self._remote_manager.get_package_revisions(pref, remote=remote)

    @api_method
    def editable_add(self, path, reference, layout, cwd):
        # Retrieve conanfile.py from target_path
        target_path = _get_conanfile_path(path=path, cwd=cwd, py=True)

        # Check the conanfile is there, and name/version matches
        ref = ConanFileReference.loads(reference, validate=True)
        target_conanfile = self._graph_manager._loader.load_class(target_path)
        if (target_conanfile.name and target_conanfile.name != ref.name) or \
                (target_conanfile.version and target_conanfile.version != ref.version):
            raise ConanException("Name and version from reference ({}) and target "
                                 "conanfile.py ({}/{}) must match".
                                 format(ref, target_conanfile.name, target_conanfile.version))

        layout_abs_path = get_editable_abs_path(layout, cwd, self._cache.conan_folder)
        if layout_abs_path:
            self._user_io.out.success("Using layout file: %s" % layout_abs_path)
        self._cache.editable_packages.add(ref, os.path.dirname(target_path), layout_abs_path)

    @api_method
    def editable_remove(self, reference):
        ref = ConanFileReference.loads(reference, validate=True)
        return self._cache.editable_packages.remove(ref)

    @api_method
    def editable_list(self):
        return {str(k): v for k, v in self._cache.editable_packages.edited_refs.items()}


Conan = ConanAPIV1


def get_graph_info(profile_names, settings, options, env, cwd, install_folder, cache, output,
                   name=None, version=None, user=None, channel=None):
    try:
        graph_info = GraphInfo.load(install_folder)
        graph_info.profile.process_settings(cache, preprocess=False)
    except IOError:  # Only if file is missing
        if install_folder:
            raise ConanException("Failed to load graphinfo file in install-folder: %s"
                                 % install_folder)
        graph_info = None

    if profile_names or settings or options or profile_names or env or not graph_info:
        if graph_info:
            # FIXME: Convert to Exception in Conan 2.0
            output.warn("Settings, options, env or profile specified. "
                        "GraphInfo found from previous install won't be used: %s\n"
                        "Don't pass settings, options or profile arguments if you want to reuse "
                        "the installed graph-info file."
                        % install_folder)

        profile = profile_from_args(profile_names, settings, options, env, cwd, cache)
        profile.process_settings(cache)
        root_ref = ConanFileReference(name, version, user, channel, validate=False)
        graph_info = GraphInfo(profile=profile, root_ref=root_ref)
        # Preprocess settings and convert to real settings
    return graph_info


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


def existing_info_files(folder):
    return os.path.exists(os.path.join(folder, CONANINFO)) and  \
           os.path.exists(os.path.join(folder, BUILD_INFO))


def get_conan_runner():
    print_commands_to_output = get_env("CONAN_PRINT_RUN_COMMANDS", False)
    generate_run_log_file = get_env("CONAN_LOG_RUN_TO_FILE", False)
    log_run_to_output = get_env("CONAN_LOG_RUN_TO_OUTPUT", True)
    runner = ConanRunner(print_commands_to_output, generate_run_log_file, log_run_to_output)
    return runner


def migrate_and_get_cache(base_folder, out, storage_folder=None):
    # Init paths
    cache = ClientCache(base_folder, storage_folder, out)

    # Migration system
    migrator = ClientMigrator(cache, Version(client_version), out)
    migrator.migrate()

    return cache
