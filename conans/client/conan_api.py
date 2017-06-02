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


def api_method_decorator(f):
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


info_only_options = ["id", "build_id", "remote", "url", "license", "requires", "update", "required",
                             "date", "author", "None"]
path_only_options = ["export_folder", "build_folder", "package_folder", "source_folder"]
str_path_only_options = ", ".join(['"%s"' % field for field in path_only_options])
str_only_options = ", ".join(['"%s"' % field for field in info_only_options])

default_manifest_folder = '.conan_manifests'


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
            conan = Conan(client_cache, user_io, get_conan_runner(), remote_manager, search_manager, os.getcwd())

        return conan

    def __init__(self, client_cache, user_io, runner, remote_manager, search_manager, cwd):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._manager = ConanManager(client_cache, user_io, runner, remote_manager, search_manager)
        self._cwd = cwd

    @api_method_decorator
    def new(self, name, header=False, pure_c=False, test=False, exports_sources=False, bare=False):
        files = get_files(name, header=header, pure_c=pure_c, test=test, exports_sources=exports_sources, bare=bare)
        save_files(self._cwd , files)
        for f in sorted(files):
            self._user_io.out.success("File saved: %s" % f)

    @api_method_decorator
    def test_package(self, path=None, profile_name=None, settings=None, options=None, env=None, scope=None,
                     test_folder=None, not_export=False, build=None, keep_source=False,
                     verify=default_manifest_folder, manifests=default_manifest_folder,
                     manifests_interactive=default_manifest_folder,
                     remote=None, update=False):
        settings = settings or []
        options = options or []
        env = env or []

        root_folder = os.path.normpath(os.path.join(self._cwd, path))
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

        profile = profile_from_args(profile_name, settings, options, env, scope, self._cwd, self._client_cache.profiles_path)
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

        manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, root_folder, self._cwd)
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
    @api_method_decorator
    def test(self, *args):
        self.test_package(*args)

    @api_method_decorator
    def package_files(self, reference, package_folder=None, profile_name=None,
                      force=False, settings=None, options=None):

        reference = ConanFileReference.loads(reference)
        package_folder = package_folder or self._cwd
        if not os.path.isabs(package_folder):
            package_folder = os.path.join(self._cwd, package_folder)
        profile = profile_from_args(profile_name, settings, options, env=None,
                                    scope=None, cwd=self._cwd, default_folder=self._client_cache.profiles_path)
        self._manager.package_files(reference=reference, package_folder=package_folder,
                                    profile=profile, force=force)

    @api_method_decorator
    def install(self, reference="", package=None, settings=None, options=None, env=None, scope=None, all=False,
                remote=None, werror=False, verify=default_manifest_folder, manifests=default_manifest_folder,
                manifests_interactive=default_manifest_folder, build=None, profile_name=None,
                update=False, generator=None, no_imports=False, filename=None):

        self._user_io.out.werror_active = werror

        try:
            ref = ConanFileReference.loads(reference)
        except:
            ref = os.path.normpath(os.path.join(self._cwd, reference))

        if all or package:  # Install packages without settings (fixed ids or all)
            if all:
                package = []
            if not reference or not isinstance(ref, ConanFileReference):
                raise ConanException("Invalid package recipe reference. "
                                     "e.g., MyPackage/1.2@user/channel")
            self._manager.download(ref, package, remote=remote)
        else:  # Classic install, package chosen with settings and options
            manifests = _parse_manifests_arguments(verify, manifests, manifests_interactive, self._cwd, self._client_cache.profiles_path)
            manifest_folder, manifest_interactive, manifest_verify = manifests
            profile = profile_from_args(profile_name, settings, options, env, scope, self._cwd,
                                        self._client_cache.profiles_path)

            self._manager.install(reference=ref,
                                  current_path=self._cwd,
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

    @api_method_decorator
    def config(self, subcommand, item):
        config_parser = ConanClientConfigParser(self._client_cache.conan_conf_path)
        if subcommand == "set":
            try:
                key, value = item.split("=", 1)
            except:
                raise ConanException("Please specify key=value")
            config_parser.set_item(key.strip(), value.strip())
        elif subcommand == "get":
            self._user_io.out.info(config_parser.get_item(item))
            return config_parser.get_item(item)
        elif subcommand == "rm":
            config_parser.rm_item(item)

    @api_method_decorator
    def info(self, reference, only=None, paths=False, remote=None, package_filter=None,
             settings=None, options=None, env=None, scope=None, build=None, profile_name=None,
             update=False, filename=None, build_order=None, graph=None, json_output=None):

        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, reference))

        if only == ["None"]:
            only = []

        if only and paths and (set(only) - set(path_only_options)):
            raise ConanException("Invalid --only value '%s' with --path specified, allowed values: [%s]."
                                 "" % (only, str_path_only_options))
        elif only and not paths and (set(only) - set(info_only_options)):
            raise ConanException("Invalid --only value '%s', allowed values: [%s].\n"
                                 "Use --only=None to show only the references." % (only, str_only_options))

        profile = profile_from_args(profile_name, settings, options, env, scope, self._cwd,
                                    self._client_cache.profiles_path)
        return self._manager.info(reference=reference,
                                  current_path=current_path,
                                  remote=remote,
                                  profile=profile,
                                  info=only,
                                  package_filter=package_filter,
                                  check_updates=update,
                                  filename=filename,
                                  build_order=build_order,
                                  build_modes=build,
                                  graph_filename=graph,
                                  show_paths=paths,
                                  json_output=json_output)

    @api_method_decorator
    def build(self, path="", source_folder=None, filename=None):

        current_path = os.getcwd()
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

    @api_method_decorator
    def package(self, reference="", package=None, build_folder=None, source_folder=None):

        current_path = os.getcwd()
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

    @api_method_decorator
    def source(self, reference, force=False):
        current_path, reference = _get_reference(reference)
        self._manager.source(current_path, reference, force)

    @api_method_decorator
    def imports(self, reference, undo=False, dest=None, filename=None):
        if undo:
            if not os.path.isabs(reference):
                current_path = os.path.normpath(os.path.join(os.getcwd(), reference))
            else:
                current_path = reference
            self._manager.imports_undo(current_path)
        else:
            current_path, reference = _get_reference(reference)
            self._manager.imports(current_path, reference, filename, dest)

    @api_method_decorator
    def export(self, user, path=None, keep_source=False, filename=None):
        current_path = os.path.abspath(path or os.getcwd())
        self._manager.export(user, current_path, keep_source, filename=filename)

    @api_method_decorator
    def remove(self, pattern, query=None, packages=None, builds=None, src=False, force=False, remote=None):
        reference = _check_query_parameter_and_get_reference(query, pattern)

        if packages is not None and query:
            raise ConanException("'-q' and '-p' parameters can't be used at the same time")

        if builds is not None and query:
            raise ConanException("'-q' and '-b' parameters can't be used at the same time")

        self._manager.remove(reference or pattern, package_ids_filter=packages, build_ids=builds,
                             src=src, force=force, remote=remote, packages_query=query)

    @api_method_decorator
    def copy(self, reference="", user_channel="", force=False, all=False, package=None):
        reference = ConanFileReference.loads(reference)
        new_ref = ConanFileReference.loads("%s/%s@%s" % (reference.name,
                                                         reference.version,
                                                         user_channel))
        if all:
            package = []
        self._manager.copy(reference, package, new_ref.user, new_ref.channel, force)

    @api_method_decorator
    def user(self, name=None, clean=False, remote=None, password=None):
        if clean:
            localdb = LocalDB(self._client_cache.localdb)
            localdb.init(clean=True)
            self._user_io.out.success("Deleted user data")
            return
        self._manager.user(remote, name, password)

    @api_method_decorator
    def search(self, pattern, query=None, remote=None, case_sensitive=False):
        reference = _check_query_parameter_and_get_reference(query, pattern)

        self._manager.search(reference or pattern,
                             remote,
                             ignorecase=not case_sensitive,
                             packages_query=query)

    @api_method_decorator
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

    @api_method_decorator
    def remote(self, subcommand, reference=None, verify_ssl=False, remote=None, url=None):
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        if subcommand == "list":
            for r in registry.remotes:
                self._user_io.out.info("%s: %s [Verify SSL: %s]" % (r.name, r.url, r.verify_ssl))
        elif subcommand == "add":
            verify = get_bool_from_text(verify_ssl)
            registry.add(remote, url, verify)
        elif subcommand == "remove":
            registry.remove(remote)
        elif subcommand == "update":
            verify = get_bool_from_text(verify_ssl)
            registry.update(remote, url, verify)
        elif subcommand == "list_ref":
            for ref, remote in registry.refs.items():
                self._user_io.out.info("%s: %s" % (ref, remote))
        elif subcommand == "add_ref":
            registry.add_ref(reference, remote)
        elif subcommand == "remove_ref":
            registry.remove_ref(reference)
        elif subcommand == "update_ref":
            registry.update_ref(reference, remote)

    @api_method_decorator
    def profile(self, subcommand, profile=None):
        if subcommand == "list":
            folder = self._client_cache.profiles_path
            if os.path.exists(folder):
                profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
                for p in sorted(profiles):
                    self._user_io.out.info(p)
            else:
                self._user_io.out.info("No profiles defined")
        elif subcommand == "show":
            p = Profile.read_file(profile, os.getcwd(), self._client_cache.profiles_path)
            Printer(self._user_io.out).print_profile(profile, p)


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


def _get_reference(ref):
    current_path = os.getcwd()
    try:
        reference = ConanFileReference.loads(ref)
    except:
        if "@" in ref:
            raise
        if not os.path.isabs(ref):
            reference = os.path.normpath(os.path.join(current_path, ref))
        else:
            reference = ref
    return current_path, reference


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
