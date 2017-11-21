import hashlib
import os
import sys

import requests

import conans
from conans import __version__ as client_version, tools
from conans.client.client_cache import ClientCache
from conans.client.conf import MIN_SERVER_COMPATIBLE_VERSION, ConanClientConfigParser
from conans.client.conf.detect import detect_defaults_settings
from conans.client.manager import ConanManager, existing_info_files
from conans.client.migrations import ClientMigrator
from conans.client.output import ConanOutput, ScopedOutput
from conans.client.profile_loader import read_profile, get_profile_path, profile_from_args, \
    read_conaninfo_profile
from conans.client.remote_manager import RemoteManager
from conans.client.remote_registry import RemoteRegistry
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClient
from conans.client.rest.version_checker import VersionCheckerRequester
from conans.client.runner import ConanRunner
from conans.client.store.localdb import LocalDB
from conans.client.cmd.test import PackageTester
from conans.client.userio import UserIO
from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.model.scope import Scopes
from conans.model.version import Version
from conans.paths import CONANFILE, get_conan_user_home, CONANFILE_TXT, CONANINFO, BUILD_INFO
from conans.search.search import DiskSearchManager, DiskSearchAdapter
from conans.util.env_reader import get_env
from conans.util.files import rmdir, save_files, exception_message_safe, save, mkdir
from conans.util.log import configure_logger
from conans.util.tracer import log_command, log_exception
from conans.client.loader_parse import load_conanfile_class
from conans.client import settings_preprocessor
from conans.tools import set_global_instances
from conans.client.cmd.uploader import CmdUpload


default_manifest_folder = '.conan_manifests'


def get_basic_requester(client_cache):
    requester = requests.Session()
    proxies = client_cache.conan_config.proxies
    if proxies:
        # Account for the requests NO_PROXY env variable, not defined as a proxy like http=
        no_proxy = proxies.pop("no_proxy", None)
        if no_proxy:
            os.environ["NO_PROXY"] = no_proxy
        requester.proxies = proxies
    return requester


def api_method(f):
    def wrapper(*args, **kwargs):
        the_self = args[0]
        try:
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

    return wrapper


def prepare_cwd(cwd):
    if cwd:
        if os.path.isabs(cwd):
            return cwd
        else:
            return os.path.abspath(cwd)
    else:
        return os.getcwd()


class ConanAPIV1(object):

    @staticmethod
    def factory():
        """Factory"""

        def instance_remote_manager(client_cache):
            requester = get_basic_requester(client_cache)
            # Verify client version against remotes
            version_checker_req = VersionCheckerRequester(requester, Version(client_version),
                                                          Version(MIN_SERVER_COMPATIBLE_VERSION),
                                                          out)
            # To handle remote connections
            put_headers = client_cache.read_put_headers()
            rest_api_client = RestApiClient(out, requester=version_checker_req,
                                            put_headers=put_headers)
            # To store user and token
            localdb = LocalDB(client_cache.localdb)
            # Wraps RestApiClient to add authentication support (same interface)
            auth_manager = ConanApiAuthManager(rest_api_client, user_io, localdb)
            # Handle remote connections
            remote_manager = RemoteManager(client_cache, auth_manager, out)
            return remote_manager

        use_color = get_env("CONAN_COLOR_DISPLAY", 1)
        if use_color and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            import colorama
            colorama.init()
            color = True
        else:
            color = False
        out = ConanOutput(sys.stdout, color)
        user_io = UserIO(out=out)

        try:
            client_cache = migrate_and_get_client_cache(get_conan_user_home(), out)
        except Exception as e:
            out.error(str(e))
            raise

        with tools.environment_append(client_cache.conan_config.env_vars):
            # Adjust CONAN_LOGGING_LEVEL with the env readed
            conans.util.log.logger = configure_logger()

            # Get the new command instance after migrations have been done
            remote_manager = instance_remote_manager(client_cache)

            # Get a search manager
            search_adapter = DiskSearchAdapter()
            search_manager = DiskSearchManager(client_cache, search_adapter)

            # Settings preprocessor
            conan = Conan(client_cache, user_io, get_conan_runner(), remote_manager, search_manager,
                          settings_preprocessor)

        return conan, client_cache, user_io

    def __init__(self, client_cache, user_io, runner, remote_manager, search_manager,
                 settings_preprocessor):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._manager = ConanManager(client_cache, user_io, runner, remote_manager, search_manager,
                                     settings_preprocessor)
        # Patch the tools module with a good requester and user_io
        set_global_instances(self._user_io.out, get_basic_requester(self._client_cache))

    @api_method
    def new(self, name, header=False, pure_c=False, test=False, exports_sources=False, bare=False,
            cwd=None, visual_versions=None, linux_gcc_versions=None, linux_clang_versions=None,
            osx_clang_versions=None, shared=None, upload_url=None, gitignore=None,
            gitlab_gcc_versions=None, gitlab_clang_versions=None):
        from conans.client.cmd.new import cmd_new
        cwd = prepare_cwd(cwd)
        files = cmd_new(name, header=header, pure_c=pure_c, test=test,
                        exports_sources=exports_sources, bare=bare,
                        visual_versions=visual_versions,
                        linux_gcc_versions=linux_gcc_versions,
                        linux_clang_versions=linux_clang_versions,
                        osx_clang_versions=osx_clang_versions, shared=shared,
                        upload_url=upload_url, gitignore=gitignore,
                        gitlab_gcc_versions=gitlab_gcc_versions,
                        gitlab_clang_versions=gitlab_clang_versions)

        save_files(cwd, files)
        for f in sorted(files):
            self._user_io.out.success("File saved: %s" % f)

    @api_method
    def test(self, path, profile_name=None, settings=None, options=None, env=None, remote=None,
             update=False, user=None, channel=None, name=None,
             version=None, build_modes=None):

        settings = settings or []
        options = options or []
        env = env or []
        cwd = os.getcwd()
        base_folder = self._abs_relative_to(path, cwd, default=cwd)
        conanfile_abs_path = self._get_conanfile_path(base_folder, "conanfile.py")

        profile = profile_from_args(profile_name, settings, options, env, None, cwd,
                                    self._client_cache)

        pt = PackageTester(self._manager, self._user_io)
        pt.install_build_and_test(conanfile_abs_path, profile, name, version, user, channel, remote,
                                  update, build_modes=build_modes)

    @api_method
    def test_package(self, profile_name=None, settings=None, options=None, env=None,
                     scope=None, test_folder=None, not_export=False, build=None, keep_source=False,
                     verify=None, manifests=None,
                     manifests_interactive=None,
                     remote=None, update=False, cwd=None, user=None, channel=None, name=None,
                     version=None):

        self._user_io.out.warn("THIS METHOD IS DEPRECATED and will be removed. "
                               "Use 'conan create' to generate binary packages for a "
                               "recipe. If you want to test a package you can use 'conan test' "
                               "command.")

        settings = settings or []
        options = options or []
        env = env or []
        cwd = prepare_cwd(cwd)

        if name and version:
            package_name = name
            package_version = version
        else:
            conanfile_path = os.path.join(cwd, "conanfile.py")
            conanfile = load_conanfile_class(conanfile_path)
            package_name = getattr(conanfile, "name", None)
            package_version = getattr(conanfile, "version", None)
        if not package_name or not package_version:
            raise ConanException("conanfile.py doesn't declare package name or version")

        test_folders = [test_folder] if test_folder else ["test_package", "test"]
        for test_folder_name in test_folders:
            test_folder = os.path.join(cwd, test_folder_name)
            test_conanfile_path = os.path.join(test_folder, "conanfile.py")
            if os.path.exists(test_conanfile_path):
                break
        else:
            raise ConanException("test folder '%s' not available, "
                                 "or it doesn't have a conanfile.py" % test_folder_name)

        sha = hashlib.sha1("".join(options + settings).encode()).hexdigest()
        build_folder = os.path.join(test_folder, "build", sha)
        rmdir(build_folder)
        # shutil.copytree(test_folder, build_folder)

        profile = profile_from_args(profile_name, settings, options, env, scope, cwd,
                                    self._client_cache)

        loader = self._manager.get_loader(profile)
        test_conanfile = loader.load_conan(test_conanfile_path, self._user_io.out, consumer=True)

        try:
            if hasattr(test_conanfile, "requirements"):
                test_conanfile.requirements()
        except Exception as e:
            raise ConanException("Error in test_package/conanfile.py requirements(). %s" % str(e))

        requirement = test_conanfile.requires.get(package_name)
        if requirement:
            if requirement.conan_reference.version != package_version:
                raise ConanException("package version is '%s', but test_package/conanfile "
                                     "is requiring version '%s'\n"
                                     "You can remove this requirement and use "
                                     "'conan test_package user/channel' instead"
                                     % (package_version, requirement.conan_reference.version))
            user = user or requirement.conan_reference.user
            channel = channel or requirement.conan_reference.channel

        if not user or not channel:
            raise ConanException("Please specify user and channel")
        conanfile_reference = ConanFileReference(package_name, package_version, user, channel)

        # Forcing an export!
        if not not_export:
            self._user_io.out.info("Exporting package recipe")
            self._manager.export(user, channel, cwd, keep_source=keep_source)

        if build is None:  # Not specified, force build the tested library
            build = [package_name]

        manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests
        self._manager.install(inject_require=conanfile_reference,
                              reference=test_folder,
                              install_folder=build_folder,
                              manifest_folder=manifest_folder,
                              manifest_verify=manifest_verify,
                              manifest_interactive=manifest_interactive,
                              remote=remote,
                              profile=profile,
                              build_modes=build,
                              update=update,
                              generators=["txt"]
                              )

        test_conanfile = os.path.join(test_folder, CONANFILE)
        self._manager.build(test_conanfile, test_folder, build_folder, package_folder=None,
                            install_folder=build_folder,
                            test=str(conanfile_reference))

    @api_method
    def create(self, profile_name=None, settings=None,
               options=None, env=None, scope=None, test_folder=None, not_export=False,
               build_modes=None,
               keep_source=False, verify=None,
               manifests=None, manifests_interactive=None,
               remote=None, update=False, conan_file_path=None, filename=None,
               user=None, channel=None, name=None, version=None, werror=False):

        settings = settings or []
        options = options or []
        env = env or []
        self._user_io.out.werror_active = werror

        cwd = os.getcwd()
        conanfile_folder = self._abs_relative_to(conan_file_path, cwd, default=cwd)

        if not name or not version:
            conanfile_abs_path = self._get_conanfile_path(conanfile_folder, filename or CONANFILE)
            conanfile = load_conanfile_class(conanfile_abs_path)
            name, version = conanfile.name, conanfile.version
            if not name or not version:
                raise ConanException("conanfile.py doesn't declare package name or version")

        reference = ConanFileReference(name, version, user, channel)
        scoped_output = ScopedOutput(str(reference), self._user_io.out)
        # Forcing an export!
        if not not_export:
            scoped_output.highlight("Exporting package recipe")
            self._manager.export(user, channel, conanfile_folder, keep_source=keep_source,
                                 name=name, version=version, filename=filename)

        if build_modes is None:  # Not specified, force build the tested library
            build_modes = [name]

        manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests
        profile = profile_from_args(profile_name, settings, options, env, scope,
                                    cwd, self._client_cache)
        self._manager.install(reference=reference,
                              install_folder=None,  # Not output anything
                              manifest_folder=manifest_folder,
                              manifest_verify=manifest_verify,
                              manifest_interactive=manifest_interactive,
                              remote=remote,
                              profile=profile,
                              build_modes=build_modes,
                              update=update,
                              filename=filename)

        base_folder = self._abs_relative_to(conan_file_path, cwd, default=cwd)

        def get_test_conanfile_path(tf):
            """Searchs in the declared test_folder or in the standard locations"""
            test_folders = [tf] if tf else ["test_package", "test"]

            for test_folder_name in test_folders:
                test_folder = os.path.join(base_folder, test_folder_name)
                test_conanfile_path = os.path.join(test_folder, "conanfile.py")
                if os.path.exists(test_conanfile_path):
                    return test_conanfile_path
            else:
                if tf:
                    raise ConanException("test folder '%s' not available, "
                                         "or it doesn't have a conanfile.py" % tf)

        test_conanfile_path = get_test_conanfile_path(test_folder)
        if test_conanfile_path:
            pt = PackageTester(self._manager, self._user_io)
            scoped_output.highlight("Testing with 'test_package'")
            pt.install_build_and_test(test_conanfile_path, profile, name, version, user,
                                      channel, remote, update)

    def _get_profile(self, profile_name, settings, options, env, cwd, install_folder):

        infos_present = existing_info_files(install_folder)

        if not infos_present:
            profile = profile_from_args(profile_name, settings, options, env=env, scope=None,
                                        cwd=cwd, client_cache=self._client_cache)
        else:
            profile = read_conaninfo_profile(install_folder)

        return profile

    def _validate_can_read_infos(self, install_folder, cwd):
        if install_folder and not existing_info_files(self._abs_relative_to(install_folder, cwd)):
                raise ConanException("The specified --install-folder doesn't contain '%s' and '%s' "
                                     "files" % (CONANINFO, BUILD_INFO))

    @staticmethod
    def _validate_one_settings_source(install_folder, profile_name, settings, options, env):
        if install_folder and existing_info_files(install_folder) and \
           (profile_name or settings or options or env):
            raise ConanException("%s and %s are found, at '%s' folder, so specifying profile, "
                                 "settings, options or env is not allowed" % (CONANINFO, BUILD_INFO,
                                                                              install_folder))

    @api_method
    def export_pkg(self, path, name, channel, source_folder=None, build_folder=None,
                   install_folder=None, profile_name=None, settings=None, options=None,
                   env=None, force=False, user=None, version=None):

        settings = settings or []
        options = options or []
        env = env or []
        cwd = os.getcwd()

        # Checks that info files exists if the install folder is specified
        self._validate_can_read_infos(install_folder, cwd)

        path = self._abs_relative_to(path, cwd)
        build_folder = self._abs_relative_to(build_folder, cwd, default=cwd)
        install_folder = self._abs_relative_to(install_folder, cwd, default=build_folder)
        source_folder = self._abs_relative_to(source_folder, cwd, default=build_folder)

        # Checks that no both settings and info files are specified
        self._validate_one_settings_source(install_folder, profile_name, settings, options, env)

        profile = self._get_profile(profile_name, settings, options, env, cwd, install_folder)
        conanfile_abs_path = self._get_conanfile_path(path, "conanfile.py")
        conanfile = load_conanfile_class(conanfile_abs_path)
        if (name and conanfile.name and conanfile.name != name) or \
           (version and conanfile.version and conanfile.version != version):
            raise ConanException("Specified name/version doesn't match with the "
                                 "name/version in the conanfile")
        self._manager.export(user, channel, path, name=name, version=version)

        if not (name and version):
            name = conanfile.name
            version = conanfile.version

        reference = ConanFileReference(name, version, user, channel)
        self._manager.export_pkg(reference, source_folder=source_folder, build_folder=build_folder,
                                 install_folder=install_folder, profile=profile, force=force)

    @api_method
    def download(self, reference, remote=None, package=None):
        # Install packages without settings (fixed ids or all)
        conan_ref = ConanFileReference.loads(reference)
        self._manager.download(conan_ref, package, remote=remote)

    @api_method
    def install_reference(self, reference, settings=None, options=None, env=None, scope=None,
                          remote=None, werror=False, verify=None, manifests=None,
                          manifests_interactive=None, build=None, profile_name=None,
                          update=False, generators=None, install_folder=None):

        self._user_io.out.werror_active = werror
        cwd = os.getcwd()
        install_folder = self._abs_relative_to(install_folder, cwd, default=cwd)

        manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests

        profile = profile_from_args(profile_name, settings, options, env, scope, cwd,
                                    self._client_cache)

        if not generators:  # We don't want the default txt
            generators = False

        mkdir(install_folder)
        self._manager.install(reference=reference, install_folder=install_folder, remote=remote,
                              profile=profile, build_modes=build, update=update,
                              manifest_folder=manifest_folder,
                              manifest_verify=manifest_verify,
                              manifest_interactive=manifest_interactive,
                              generators=generators,
                              cwd=cwd, install_reference=True)

    @api_method
    def install(self, path="", settings=None, options=None, env=None, scope=None,
                remote=None, werror=False, verify=None, manifests=None,
                manifests_interactive=None, build=None, profile_name=None,
                update=False, generators=None, no_imports=False, filename=None,
                install_folder=None):

        self._user_io.out.werror_active = werror

        cwd = os.getcwd()
        install_folder = self._abs_relative_to(install_folder, cwd, default=cwd)
        conanfile_folder = self._abs_relative_to(path, cwd, default=cwd)

        manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests

        profile = profile_from_args(profile_name, settings, options, env, scope, cwd,
                                    self._client_cache)

        self._manager.install(reference=conanfile_folder,
                              install_folder=install_folder,
                              remote=remote,
                              profile=profile,
                              build_modes=build,
                              filename=filename,
                              update=update,
                              manifest_folder=manifest_folder,
                              manifest_verify=manifest_verify,
                              manifest_interactive=manifest_interactive,
                              generators=generators,
                              no_imports=no_imports)

    @api_method
    def config_get(self, item):
        config_parser = ConanClientConfigParser(self._client_cache.conan_conf_path)
        self._user_io.out.info(config_parser.get_item(item))
        return config_parser.get_item(item)

    @api_method
    def config_set(self, item, value):
        config_parser = ConanClientConfigParser(self._client_cache.conan_conf_path)
        config_parser.set_item(item, value)

    @api_method
    def config_rm(self, item):
        config_parser = ConanClientConfigParser(self._client_cache.conan_conf_path)
        config_parser.rm_item(item)

    @api_method
    def config_install(self, item):
        from conans.client.conf.config_installer import configuration_install
        return configuration_install(item, self._client_cache, self._user_io.out, self._runner)

    @api_method
    def info_build_order(self, reference, settings=None, options=None, env=None, scope=None,
                         profile_name=None, filename=None, remote=None, build_order=None,
                         check_updates=None, build_folder=None):

        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, reference))

        profile = profile_from_args(profile_name, settings, options, env, scope, build_folder,
                                    self._client_cache)
        graph = self._manager.info_build_order(reference, profile, filename, build_order,
                                               remote, check_updates)
        return graph

    @api_method
    def info_nodes_to_build(self, reference, build_modes, settings=None, options=None, env=None,
                            scope=None, profile_name=None, filename=None, remote=None,
                            check_updates=None, build_folder=None):

        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, reference))

        profile = profile_from_args(profile_name, settings, options, env, scope, build_folder,
                                    self._client_cache)
        ret = self._manager.info_nodes_to_build(reference, profile, filename, build_modes, remote,
                                                check_updates)
        ref_list, project_reference = ret
        return ref_list, project_reference

    @api_method
    def info_get_graph(self, reference, remote=None, settings=None, options=None, env=None,
                       scope=None, profile_name=None, update=False, filename=None,
                       build_folder=None):

        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, reference))

        profile = profile_from_args(profile_name, settings, options, env, scope, build_folder,
                                    self._client_cache)
        ret = self._manager.info_get_graph(reference=reference,
                                           remote=remote, profile=profile, check_updates=update,
                                           filename=filename)
        deps_graph, graph_updates_info, project_reference = ret
        return deps_graph, graph_updates_info, project_reference

    @api_method
    def build(self, path, source_folder=None, package_folder=None, filename=None,
              build_folder=None, install_folder=None):

        cwd = os.getcwd()
        conanfile_folder = self._abs_relative_to(path, cwd)
        build_folder = self._abs_relative_to(build_folder, cwd, default=cwd)
        install_folder = self._abs_relative_to(install_folder, cwd, default=build_folder)
        source_folder = self._abs_relative_to(source_folder, cwd, default=conanfile_folder)
        default_pkg_folder = os.path.join(build_folder, "package")
        package_folder = self._abs_relative_to(package_folder, cwd, default=default_pkg_folder)

        conanfile_abs_path = self._get_conanfile_path(conanfile_folder, filename)
        if conanfile_abs_path.endswith(".txt"):
              raise ConanException("A conanfile.py is needed to call 'conan build' "
                                   "(not valid conanfile.txt)")

        self._manager.build(conanfile_abs_path, source_folder, build_folder, package_folder,
                            install_folder)

    @api_method
    def package(self, path, build_folder, package_folder, source_folder=None, install_folder=None):
        cwd = os.getcwd()
        conanfile_folder = self._abs_relative_to(path, cwd)
        build_folder = self._abs_relative_to(build_folder, cwd, default=cwd)
        install_folder = self._abs_relative_to(install_folder, cwd, default=build_folder)
        source_folder = self._abs_relative_to(source_folder, cwd, default=conanfile_folder)
        default_pkg = os.path.join(build_folder, "package")
        package_folder = self._abs_relative_to(package_folder, cwd, default=default_pkg)
        self._manager.local_package(package_folder, conanfile_folder, build_folder, source_folder,
                                    install_folder)

    @api_method
    def source(self, path, source_folder=None, info_folder=None):
        cwd = os.getcwd()
        path = self._abs_relative_to(path, cwd)
        source_folder = self._abs_relative_to(source_folder, cwd, default=cwd)
        info_folder = self._abs_relative_to(info_folder, cwd, default=cwd)

        mkdir(source_folder)
        if not os.path.exists(info_folder):
            raise ConanException("Specified info-folder doesn't exist")

        conanfile_abs_path = self._get_conanfile_path(path, CONANFILE)
        self._manager.source(conanfile_abs_path, source_folder, info_folder)

    @staticmethod
    def _abs_relative_to(path, base_relative, default=None):
        """Gets an absolute path from "path" parameter, prepending base_relative if not abs yet.
        If path is none, will return the 'default'"""
        if not path:
            return default
        if not os.path.isabs(path):
            return os.path.normpath(os.path.join(base_relative, path))
        else:
            return path

    @staticmethod
    def _get_conanfile_path(conanfile_folder, the_filename=None):
        def raise_if_not_exists(some_path):
            if not os.path.exists(some_path):
                raise ConanException("Conanfile not found: %s" % some_path)

        if the_filename:
            conanfile_path = os.path.join(conanfile_folder, the_filename)
            raise_if_not_exists(conanfile_path)
        else:
            conanfile_path = os.path.join(conanfile_folder, CONANFILE)
            if not os.path.exists(conanfile_path):
                conanfile_path = os.path.join(conanfile_folder, CONANFILE_TXT)
                raise_if_not_exists(conanfile_path)
        return conanfile_path


    @api_method
    def imports(self, path, dest=None, filename=None, info_folder=None):
        """
        :param path: Path to the conanfile
        :param dest: Dir to put the imported files. (Abs path or relative to cwd)
        :param filename: Alternative name of the conanfile. Default: conanfile.py or conanfile.txt
        :param build_folder: Dir where the conaninfo.txt and conanbuildinfo.txt files are
        :return: None
        """
        cwd = os.getcwd()
        conanfile_folder = self._abs_relative_to(path, cwd)
        info_folder = self._abs_relative_to(info_folder, cwd, default=cwd)
        dest = self._abs_relative_to(dest, cwd, default=cwd)

        mkdir(dest)
        conanfile_abs_path = self._get_conanfile_path(conanfile_folder, filename)
        self._manager.imports(conanfile_abs_path, dest, info_folder)

    @api_method
    def imports_undo(self, manifest_path):
        manifest_path = self._abs_relative_to(manifest_path, os.getcwd())
        self._manager.imports_undo(manifest_path)

    @api_method
    def export(self, user, channel, path=None, keep_source=False, filename=None, cwd=None,
               name=None, version=None):
        cwd = prepare_cwd(cwd)
        current_path = os.path.abspath(path or cwd)
        self._manager.export(user, channel, current_path, keep_source, filename=filename, name=name,
                             version=version)

    @api_method
    def remove(self, pattern, query=None, packages=None, builds=None, src=False, force=False,
               remote=None, outdated=False):
        self._manager.remove(pattern, package_ids_filter=packages, build_ids=builds,
                             src=src, force=force, remote=remote, packages_query=query,
                             outdated=outdated)

    @api_method
    def copy(self, reference, user_channel, force=False, packages=None):
        """
        param packages: None=No binaries, True=All binaries, else list of IDs
        """
        from conans.client.cmd.copy import cmd_copy
        # FIXME: conan copy does not support short-paths in Windows
        cmd_copy(reference, user_channel, packages, self._client_cache,
                 self._user_io, self._manager._remote_manager, force=force)

    @api_method
    def user(self, name=None, clean=False, remote=None, password=None):
        if clean:
            localdb = LocalDB(self._client_cache.localdb)
            localdb.init(clean=True)
            self._user_io.out.success("Deleted user data")
            return
        self._manager.user(remote, name, password)

    @api_method
    def search_recipes(self, pattern, remote=None, case_sensitive=False):
        refs = self._manager.search_recipes(pattern, remote, ignorecase=not case_sensitive)
        return refs

    @api_method
    def search_packages(self, reference, query=None, remote=None, outdated=False):
        ret = self._manager.search_packages(reference, remote, packages_query=query,
                                            outdated=outdated)
        return ret

    @api_method
    def upload(self, pattern, package=None, remote=None, all_packages=False, force=False,
               confirm=False, retry=2, retry_wait=5, skip_upload=False, integrity_check=False):
        """ Uploads a package recipe and the generated binary packages to a specified remote
        """
        uploader = CmdUpload(self._client_cache, self._user_io, self._manager._remote_manager,
                             self._manager._search_manager, remote)
        return uploader.upload(pattern, package, all_packages, force, confirm, retry,
                               retry_wait, skip_upload, integrity_check)

    @api_method
    def remote_list(self):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.remotes

    @api_method
    def remote_add(self, remote, url, verify_ssl=True, insert=None):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.add(remote, url, verify_ssl, insert)

    @api_method
    def remote_remove(self, remote):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.remove(remote)

    @api_method
    def remote_update(self, remote, url, verify_ssl=True, insert=None):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.update(remote, url, verify_ssl, insert)

    @api_method
    def remote_list_ref(self):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.refs

    @api_method
    def remote_add_ref(self, reference, remote):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.add_ref(reference, remote)

    @api_method
    def remote_remove_ref(self, reference):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.remove_ref(reference)

    @api_method
    def remote_update_ref(self, reference, remote):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.update_ref(reference, remote)

    @api_method
    def profile_list(self):
        folder = self._client_cache.profiles_path
        if os.path.exists(folder):
            return [name for name in os.listdir(folder)
                    if not os.path.isdir(os.path.join(folder, name))]
        else:
            self._user_io.out.info("No profiles defined")
            return []

    @api_method
    def create_profile(self, profile_name, detect=False):
        profile_path = get_profile_path(profile_name, self._client_cache.profiles_path, os.getcwd(),
                                        exists=False)
        if os.path.exists(profile_path):
            raise ConanException("Profile already exists")

        profile = Profile()
        if detect:
            settings = detect_defaults_settings(self._user_io.out)
            for name, value in settings:
                profile.settings[name] = value

        contents = profile.dumps()
        save(profile_path, contents)
        self._user_io.out.info("Empty profile created: %s" % profile_path)
        return profile_path

    @staticmethod
    def _get_profile_keys(key):
        # settings.compiler.version => settings, compiler.version
        tmp = key.split(".")
        first_key = tmp[0]
        rest_key = ".".join(tmp[1:]) if len(tmp) > 1 else None
        if first_key not in ("build_requires", "settings", "options", "scopes", "env"):
            raise ConanException("Invalid specified key: %s" % key)

        return first_key, rest_key

    @api_method
    def update_profile(self, profile_name, key, value):
        first_key, rest_key = self._get_profile_keys(key)

        profile, _ = read_profile(profile_name, os.getcwd(), self._client_cache.profiles_path)
        if first_key == "settings":
            profile.settings[rest_key] = value
        elif first_key == "options":
            tmp = OptionsValues([(rest_key, value)])
            profile.options.update(tmp)
        elif first_key == "env":
            profile.env_values.update(EnvValues.loads("%s=%s" % (rest_key, value)))
        elif first_key == "scopes":
            profile.update_scopes(Scopes.from_list(["%s=%s" % (rest_key, value)]))
        elif first_key == "build_requires":
            raise ConanException("Edit the profile manually to change the build_requires")

        contents = profile.dumps()
        profile_path = get_profile_path(profile_name, self._client_cache.profiles_path, os.getcwd())
        save(profile_path, contents)

    @api_method
    def get_profile_key(self, profile_name, key):
        first_key, rest_key = self._get_profile_keys(key)
        profile, _ = read_profile(profile_name, os.getcwd(), self._client_cache.profiles_path)
        try:
            if first_key == "settings":
                return profile.settings[rest_key]
            elif first_key == "options":
                return dict(profile.options.as_list())[rest_key]
            elif first_key == "env":
                package = None
                var = rest_key
                if ":" in rest_key:
                    package, var = rest_key.split(":")
                return profile.env_values.data[package][var]
            elif first_key == "build_requires":
                raise ConanException("List the profile manually to see the build_requires")
        except KeyError:
            raise ConanException("Key not found: '%s'" % key)

    @api_method
    def delete_profile_key(self, profile_name, key):
        first_key, rest_key = self._get_profile_keys(key)
        profile, _ = read_profile(profile_name, os.getcwd(), self._client_cache.profiles_path)

        # For options, scopes, env vars
        try:
            package, name = rest_key.split(":")
        except ValueError:
            package = None
            name = rest_key

        try:
            if first_key == "settings":
                del profile.settings[rest_key]
            elif first_key == "options":
                profile.options.remove(name, package)
            elif first_key == "env":
                profile.env_values.remove(name, package)
            elif first_key == "scopes":
                profile.scopes.remove(name, package)
            elif first_key == "build_requires":
                raise ConanException("Edit the profile manually to delete a build_require")
        except KeyError:
            raise ConanException("Profile key '%s' doesn't exist" % key)

        contents = profile.dumps()
        profile_path = get_profile_path(profile_name, self._client_cache.profiles_path, os.getcwd())
        save(profile_path, contents)

    @api_method
    def read_profile(self, profile=None):
        p, _ = read_profile(profile, os.getcwd(), self._client_cache.profiles_path)
        return p

    @api_method
    def get_path(self, reference, package_id=None, path=None, remote=None):
        reference = ConanFileReference.loads(str(reference))
        return self._manager.get_path(reference, package_id, path, remote)

    @api_method
    def export_alias(self, reference, target_reference):
        reference = ConanFileReference.loads(str(reference))
        target_reference = ConanFileReference.loads(str(target_reference))
        return self._manager.export_alias(reference, target_reference)


Conan = ConanAPIV1


def _check_query_parameter_and_get_reference(query, pattern):
    reference = None
    if pattern:
        try:
            reference = ConanFileReference.loads(pattern)
        except ConanException:
            if query is not None:
                raise ConanException("-q parameter only allowed with a valid recipe "
                                     "reference as search pattern. e.j conan search "
                                     "MyPackage/1.2@user/channel -q \"os=Windows\"")
    return reference


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


def _get_reference(ref, cwd=None):
    try:
        reference = ConanFileReference.loads(ref)
    except:
        if "@" in ref:
            raise
        if not os.path.isabs(ref):
            reference = os.path.normpath(os.path.join(cwd, ref))
        else:
            reference = ref
    return cwd, reference


def migrate_and_get_client_cache(base_folder, out, storage_folder=None):
    # Init paths
    client_cache = ClientCache(base_folder, storage_folder, out)

    # Migration system
    migrator = ClientMigrator(client_cache, Version(client_version), out)
    migrator.migrate()

    return client_cache

