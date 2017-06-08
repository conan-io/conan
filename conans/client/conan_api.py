import hashlib
import os
import sys

import requests
from collections import defaultdict, OrderedDict

import conans
from conans import __version__ as CLIENT_VERSION, tools
from conans.client.client_cache import ClientCache
from conans.client.conf import MIN_SERVER_COMPATIBLE_VERSION, ConanClientConfigParser
from conans.client.loader import load_consumer_conanfile
from conans.client.manager import ConanManager
from conans.client.migrations import ClientMigrator
from conans.client.new import get_files
from conans.client.output import ConanOutput, Color
from conans.client.printer import Printer
from conans.client.remote_manager import RemoteManager
from conans.client.remote_registry import RemoteRegistry
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClient
from conans.client.rest.version_checker import VersionCheckerRequester
from conans.client.runner import ConanRunner
from conans.client.store.localdb import LocalDB
from conans.client.userio import UserIO
from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference, is_a_reference
from conans.model.scope import Scopes
from conans.model.version import Version
from conans.paths import CONANFILE, conan_expand_user
from conans.search.search import DiskSearchManager, DiskSearchAdapter
from conans.util.config_parser import get_bool_from_text
from conans.util.env_reader import get_env
from conans.util.files import rmdir, save_files, exception_message_safe
from conans.util.log import logger, configure_logger
from conans.util.tracer import log_command, log_exception


def api_method(f):
    def wrapper(*args, **kwargs):
        the_self = args[0]
        try:
            log_command(f.__name__, kwargs)
            with tools.environment_append(the_self._client_cache.conan_config.env_vars):
                return f(*args, **kwargs)
        except ConanException as exc:
            # import traceback
            # logger.debug(traceback.format_exc())
            msg = exception_message_safe(exc)
            the_self._user_io.out.error(msg)
            try:
                log_exception(exc, msg)
            except:
                pass
            raise
        except Exception as exc:
            import traceback
            print(traceback.format_exc())
            msg = exception_message_safe(exc)
            try:
                log_exception(exc, msg)
            except:
                pass
            raise exc

    return wrapper


default_manifest_folder = '.conan_manifests'


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
            requester = requests.Session()
            requester.proxies = client_cache.conan_config.proxies
            # Verify client version against remotes
            version_checker_requester = VersionCheckerRequester(requester, Version(CLIENT_VERSION),
                                                                Version(MIN_SERVER_COMPATIBLE_VERSION),
                                                                out)
            # To handle remote connections
            put_headers = client_cache.read_put_headers()
            rest_api_client = RestApiClient(out, requester=version_checker_requester, put_headers=put_headers)
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

        user_folder = os.getenv("CONAN_USER_HOME", conan_expand_user("~"))

        try:
            client_cache = migrate_and_get_client_cache(user_folder, out)
        except Exception as e:
            out.error(str(e))
            sys.exit(True)

        with tools.environment_append(client_cache.conan_config.env_vars):
            # Adjust CONAN_LOGGING_LEVEL with the env readed
            conans.util.log.logger = configure_logger()

            # Get the new command instance after migrations have been done
            remote_manager = instance_remote_manager(client_cache)

            # Get a search manager
            search_adapter = DiskSearchAdapter()
            search_manager = DiskSearchManager(client_cache, search_adapter)
            conan = Conan(client_cache, user_io, get_conan_runner(), remote_manager, search_manager)

        return conan

    def __init__(self, client_cache, user_io, runner, remote_manager, search_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._manager = ConanManager(client_cache, user_io, runner, remote_manager, search_manager)


    @api_method
    def new(self, name, header=False, pure_c=False, test=False, exports_sources=False, bare=False, cwd=None):
        cwd = prepare_cwd(cwd)
        files = get_files(name, header=header, pure_c=pure_c, test=test, exports_sources=exports_sources, bare=bare)
        save_files(cwd, files)
        for f in sorted(files):
            self._user_io.out.success("File saved: %s" % f)

    @api_method
    def test_package(self, path=None, profile_name=None, settings=None, options=None, env=None, scope=None,
                     test_folder=None, not_export=False, build=None, keep_source=False,
                     verify=default_manifest_folder, manifests=default_manifest_folder,
                     manifests_interactive=default_manifest_folder,
                     remote=None, update=False, cwd=None):
        settings = settings or []
        options = options or []
        env = env or []
        cwd = prepare_cwd(cwd)

        root_folder = os.path.normpath(os.path.join(cwd, path))
        if test_folder:
            test_folder_name = test_folder
            test_folder = os.path.join(root_folder, test_folder_name)
            test_conanfile = os.path.join(test_folder, "conanfile.py")
            if not os.path.exists(test_conanfile):
                raise ConanException("test folder '%s' not available, "
                                     "or it doesn't have a conanfile.py" % test_folder)
        else:
            for name in ["test_package", "test"]:
                test_folder_name = name
                test_folder = os.path.join(root_folder, test_folder_name)
                test_conanfile = os.path.join(test_folder, "conanfile.py")
                if os.path.exists(test_conanfile):
                    break
            else:
                raise ConanException("test folder 'test_package' not available, "
                                     "or it doesn't have a conanfile.py")

        options = options or []
        settings = settings or []

        sha = hashlib.sha1("".join(options + settings).encode()).hexdigest()
        build_folder = os.path.join(test_folder, "build", sha)
        rmdir(build_folder)
        # shutil.copytree(test_folder, build_folder)

        profile = profile_from_args(profile_name, settings, options, env, scope, cwd, self._client_cache.profiles_path)
        conanfile = load_consumer_conanfile(test_conanfile, "",
                                            self._client_cache.settings, self._runner,
                                            self._user_io.out)
        try:
            # convert to list from ItemViews required for python3
            if hasattr(conanfile, "requirements"):
                conanfile.requirements()
            reqs = list(conanfile.requires.items())
            first_dep = reqs[0][1].conan_reference
        except Exception:
            raise ConanException("Unable to retrieve first requirement of test conanfile.py")

        # Forcing an export!
        if not not_export:
            self._user_io.out.info("Exporting package recipe")
            user_channel = "%s/%s" % (first_dep.user, first_dep.channel)
            self._manager.export(user_channel, root_folder, keep_source=keep_source)

        lib_to_test = first_dep.name + "*"
        # Get False or a list of patterns to check
        if build is None and lib_to_test:  # Not specified, force build the tested library
            build = [lib_to_test]

        manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, root_folder, cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests
        self._manager.install(reference=test_folder,
                              current_path=build_folder,
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
        self._manager.build(test_conanfile, test_folder, build_folder, test=True)

    # Alias to test
    @api_method
    def test(self, *args):
        self.test_package(*args)

    @api_method
    def package_files(self, reference, package_folder=None, profile_name=None,
                      force=False, settings=None, options=None, cwd=None):

        cwd = prepare_cwd(cwd)

        reference = ConanFileReference.loads(reference)
        package_folder = package_folder or cwd
        if not os.path.isabs(package_folder):
            package_folder = os.path.join(cwd, package_folder)
        profile = profile_from_args(profile_name, settings, options, env=None,
                                    scope=None, cwd=cwd, default_folder=self._client_cache.profiles_path)
        self._manager.package_files(reference=reference, package_folder=package_folder,
                                    profile=profile, force=force)

    @api_method
    def install(self, reference="", package=None, settings=None, options=None, env=None, scope=None, all=False,
                remote=None, werror=False, verify=default_manifest_folder, manifests=default_manifest_folder,
                manifests_interactive=default_manifest_folder, build=None, profile_name=None,
                update=False, generator=None, no_imports=False, filename=None, cwd=None):

        self._user_io.out.werror_active = werror
        cwd = prepare_cwd(cwd)

        try:
            ref = ConanFileReference.loads(reference)
        except:
            ref = os.path.normpath(os.path.join(cwd, reference))

        if all or package:  # Install packages without settings (fixed ids or all)
            if all:
                package = []
            if not reference or not isinstance(ref, ConanFileReference):
                raise ConanException("Invalid package recipe reference. "
                                     "e.g., MyPackage/1.2@user/channel")
            self._manager.download(ref, package, remote=remote)
        else:  # Classic install, package chosen with settings and options
            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, cwd, self._client_cache.profiles_path)
            manifest_folder, manifest_interactive, manifest_verify = manifests
            profile = profile_from_args(profile_name, settings, options, env, scope, cwd,
                                        self._client_cache.profiles_path)

            self._manager.install(reference=ref,
                                  current_path=cwd,
                                  remote=remote,
                                  profile=profile,
                                  build_modes=build,
                                  filename=filename,
                                  update=update,
                                  manifest_folder=manifest_folder,
                                  manifest_verify=manifest_verify,
                                  manifest_interactive=manifest_interactive,
                                  generators=generator,
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
    def info_build_order(self, reference, settings=None, options=None, env=None, scope=None, profile_name=None,
                         filename=None, remote=None, build_order=None, check_updates=None, cwd=None):

        current_path = prepare_cwd(cwd)
        try:
            reference = ConanFileReference.loads(reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, reference))

        profile = profile_from_args(profile_name, settings, options, env, scope, cwd, self._client_cache.profiles_path)
        graph = self._manager.info_build_order(reference, profile, filename, build_order, remote, check_updates, cwd=cwd)
        return graph

    @api_method
    def info_nodes_to_build(self, reference, build_modes, settings=None, options=None, env=None, scope=None,
                            profile_name=None, filename=None, remote=None, check_updates=None, cwd=None):

        current_path = prepare_cwd(cwd)
        try:
            reference = ConanFileReference.loads(reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, reference))

        profile = profile_from_args(profile_name, settings, options, env, scope, cwd, self._client_cache.profiles_path)
        ret = self._manager.info_nodes_to_build(reference, profile, filename, build_modes, remote, check_updates, cwd)
        ref_list, project_reference = ret
        return ref_list, project_reference

    @api_method
    def info_get_graph(self, reference, remote=None, settings=None, options=None, env=None, scope=None,
                       profile_name=None, update=False, filename=None, cwd=None):

        current_path = prepare_cwd(cwd)
        try:
            reference = ConanFileReference.loads(reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, reference))

        profile = profile_from_args(profile_name, settings, options, env, scope, current_path,
                                    self._client_cache.profiles_path)
        ret = self._manager.info_get_graph(reference=reference, current_path=current_path, remote=remote,
                                           profile=profile, check_updates=update, filename=filename)
        deps_graph, graph_updates_info, project_reference = ret
        return deps_graph, graph_updates_info, project_reference

    @api_method
    def build(self, path="", source_folder=None, filename=None, cwd=None):

        current_path = prepare_cwd(cwd)
        if path:
            root_path = os.path.abspath(path)
        else:
            root_path = current_path

        build_folder = current_path
        source_folder = source_folder or root_path
        if not os.path.isabs(source_folder):
            source_folder = os.path.normpath(os.path.join(current_path, source_folder))

        if filename and filename.endswith(".txt"):
            raise ConanException("A conanfile.py is needed to call 'conan build'")
        conanfile_path = os.path.join(root_path, filename or CONANFILE)
        self._manager.build(conanfile_path, source_folder, build_folder)

    @api_method
    def package(self, reference="", package=None, build_folder=None, source_folder=None, cwd=None):

        current_path = prepare_cwd(cwd)
        try:
            self._manager.package(ConanFileReference.loads(reference), package)
        except:
            if "@" in reference:
                raise
            recipe_folder = reference
            if not os.path.isabs(recipe_folder):
                recipe_folder = os.path.normpath(os.path.join(current_path, recipe_folder))
            build_folder = build_folder or current_path
            if not os.path.isabs(build_folder):
                build_folder = os.path.normpath(os.path.join(current_path, build_folder))
            package_folder = current_path
            source_folder = source_folder or recipe_folder
            self._manager.local_package(package_folder, recipe_folder, build_folder, source_folder)

    @api_method
    def source(self, reference, force=False, cwd=None):
        cwd = prepare_cwd(cwd)
        current_path, reference = _get_reference(reference, cwd)
        self._manager.source(current_path, reference, force)

    @api_method
    def imports(self, reference, undo=False, dest=None, filename=None, cwd=None):
        cwd = prepare_cwd(cwd)

        if undo:
            if not os.path.isabs(reference):
                current_path = os.path.normpath(os.path.join(cwd, reference))
            else:
                current_path = reference
            self._manager.imports_undo(current_path)
        else:
            cwd = prepare_cwd(cwd)
            current_path, reference = _get_reference(reference, cwd)
            self._manager.imports(current_path, reference, filename, dest)

    @api_method
    def export(self, user, path=None, keep_source=False, filename=None, cwd=None):
        cwd = prepare_cwd(cwd)
        current_path = os.path.abspath(path or cwd)
        self._manager.export(user, current_path, keep_source, filename=filename)

    @api_method
    def remove(self, pattern, query=None, packages=None, builds=None, src=False, force=False, remote=None):
        self._manager.remove(pattern, package_ids_filter=packages, build_ids=builds,
                             src=src, force=force, remote=remote, packages_query=query)


    @api_method
    def copy(self, reference="", user_channel="", force=False, all=False, package=None):
        reference = ConanFileReference.loads(reference)
        new_ref = ConanFileReference.loads("%s/%s@%s" % (reference.name,
                                                         reference.version,
                                                         user_channel))
        if all:
            package = []
        self._manager.copy(reference, package, new_ref.user, new_ref.channel, force)

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
    def search_packages(self, reference, query=None, remote=None):
        ret = self._manager.search_packages(reference, remote, packages_query=query)
        return ret

    @api_method
    def upload(self, pattern, package=None, remote=None, all=False, force=False, confirm=False, retry=2, retry_wait=5,
               skip_upload=False):
        """ Uploads a package recipe and the generated binary packages to a specified remote
        """
        if package and not is_a_reference(pattern):
            raise ConanException("-p parameter only allowed with a valid recipe reference, not with a pattern")

        self._manager.upload(pattern, package,
                             remote, all_packages=all,
                             force=force, confirm=confirm, retry=retry,
                             retry_wait=retry_wait, skip_upload=skip_upload)

    @api_method
    def remote_list(self):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        for r in registry.remotes:
            self._user_io.out.info("%s: %s [Verify SSL: %s]" % (r.name, r.url, r.verify_ssl))

    @api_method
    def remote_add(self, remote, url, verify_ssl=True):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.add(remote, url, verify_ssl)

    @api_method
    def remote_remove(self, remote):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.remove(remote)

    @api_method
    def remote_update(self, remote, url, verify_ssl=True):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return registry.update(remote, url, verify_ssl)

    @api_method
    def remote_list_ref(self):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        for ref, remote in registry.refs.items():
            self._user_io.out.info("%s: %s" % (ref, remote))

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
    def profile(self, subcommand, profile=None, cwd=None):
        cwd = prepare_cwd(cwd)
        if subcommand == "list":
            folder = self._client_cache.profiles_path
            if os.path.exists(folder):
                profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
                for p in sorted(profiles):
                    self._user_io.out.info(p)
            else:
                self._user_io.out.info("No profiles defined")
        elif subcommand == "show":
            p = Profile.read_file(profile, cwd, self._client_cache.profiles_path)
            Printer(self._user_io.out).print_profile(profile, p)


Conan = ConanAPIV1


def _parse_manifests_arguments(verify, manifests, manifests_interactive, reference, current_path):
    if manifests and manifests_interactive:
        raise ConanException("Do not specify both manifests and "
                             "manifests-interactive arguments")
    if verify and (manifests or manifests_interactive):
        raise ConanException("Do not specify both 'verify' and "
                             "'manifests' or 'manifests-interactive' arguments")
    manifest_folder = verify or manifests or manifests_interactive
    if manifest_folder:
        if not os.path.isabs(manifest_folder):
            if isinstance(reference, ConanFileReference):
                manifest_folder = os.path.join(current_path, manifest_folder)
            else:
                manifest_folder = os.path.join(reference, manifest_folder)
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
    migrator = ClientMigrator(client_cache, Version(CLIENT_VERSION), out)
    migrator.migrate()

    return client_cache


# Profile helpers


def profile_from_args(profile, settings, options, env, scope, cwd, default_folder):
    """ Return a Profile object, as the result of merging a potentially existing Profile
    file and the args command-line arguments
    """
    file_profile = Profile.read_file(profile, cwd, default_folder)
    args_profile = _profile_parse_args(settings, options, env, scope)

    if file_profile:
        file_profile.update(args_profile)
        return file_profile
    else:
        return args_profile


def _profile_parse_args(settings, options, envs, scopes):
    """ return a Profile object result of parsing raw data
    """
    def _get_tuples_list_from_extender_arg(items):
        if not items:
            return []
        # Validate the pairs
        for item in items:
            chunks = item.split("=", 1)
            if len(chunks) != 2:
                raise ConanException("Invalid input '%s', use 'name=value'" % item)
        return [(item[0], item[1]) for item in [item.split("=", 1) for item in items]]

    def _get_simple_and_package_tuples(items):
        """Parse items like "thing:item=value or item2=value2 and returns a tuple list for
        the simple items (name, value) and a dict for the package items
        {package: [(item, value)...)], ...}
        """
        simple_items = []
        package_items = defaultdict(list)
        tuples = _get_tuples_list_from_extender_arg(items)
        for name, value in tuples:
            if ":" in name:  # Scoped items
                tmp = name.split(":", 1)
                ref_name = tmp[0]
                name = tmp[1]
                package_items[ref_name].append((name, value))
            else:
                simple_items.append((name, value))
        return simple_items, package_items

    def _get_env_values(env, package_env):
        env_values = EnvValues()
        for name, value in env:
            env_values.add(name, EnvValues.load_value(value))
        for package, data in package_env.items():
            for name, value in data:
                env_values.add(name, EnvValues.load_value(value), package)
        return env_values

    result = Profile()
    options = _get_tuples_list_from_extender_arg(options)
    result.options = OptionsValues(options)
    env, package_env = _get_simple_and_package_tuples(envs)
    env_values = _get_env_values(env, package_env)
    result.env_values = env_values
    settings, package_settings = _get_simple_and_package_tuples(settings)
    result.settings = OrderedDict(settings)
    for pkg, values in package_settings.items():
        result.package_settings[pkg] = OrderedDict(values)
    result.scopes = Scopes.from_list(scopes) if scopes else Scopes()
    return result
