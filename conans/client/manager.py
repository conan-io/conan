import os
import time
from collections import OrderedDict

from conans.paths import (CONANFILE, CONANINFO, CONANFILE_TXT, BUILD_INFO, CONANENV)
from conans.client.loader import ConanFileLoader
from conans.client.export import export_conanfile
from conans.client.deps_builder import DepsBuilder
from conans.client.userio import UserIO
from conans.client.installer import ConanInstaller
from conans.util.files import save, load, rmdir, normalize
from conans.util.log import logger
from conans.client.uploader import ConanUploader
from conans.client.printer import Printer
from conans.errors import NotFoundException, ConanException
from conans.client.generators import write_generators
from conans.client.importer import run_imports, undo_imports
from conans.model.ref import ConanFileReference, PackageReference
from conans.client.remover import ConanRemover
from conans.model.info import ConanInfo
from conans.model.values import Values
from conans.model.options import OptionsValues
from conans.model.build_info import DepsCppInfo, CppInfo
from conans.client import packager
from conans.client.detect import detected_os
from conans.client.package_copier import PackageCopier
from conans.client.output import ScopedOutput
from conans.client.proxy import ConanProxy
from conans.client.remote_registry import RemoteRegistry
from conans.model.scope import Scopes
from conans.client.client_cache import ClientCache
from conans.client.source import config_source, config_source_local
from conans.client.manifest_manager import ManifestManager
from conans.model.env_info import EnvInfo, DepsEnvInfo
from conans.tools import environment_append
from conans.client.require_resolver import RequireResolver
from conans.model.profile import Profile


def get_user_channel(text):
    tokens = text.split('/')
    try:
        user = tokens[0]
        channel = tokens[1]
    except IndexError:
        channel = "testing"
    return user, channel


class ConanManager(object):
    """ Manage all the commands logic  The main entry point for all the client
    business logic
    """
    def __init__(self, client_cache, user_io, runner, remote_manager, search_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._remote_manager = remote_manager
        self._current_scopes = None
        self._search_manager = search_manager

    def _loader(self, current_path=None, user_settings_values=None, package_settings=None,
                user_options_values=None, scopes=None, env=None, package_env=None):

        # The disk settings definition, already including the default disk values
        settings = self._client_cache.settings

        options = OptionsValues()
        conaninfo_scopes = Scopes()

        if current_path:
            conan_info_path = os.path.join(current_path, CONANINFO)
            if os.path.exists(conan_info_path):
                existing_info = ConanInfo.load_file(conan_info_path)
                settings.values = existing_info.full_settings
                options = existing_info.full_options  # Take existing options from conaninfo.txt
                conaninfo_scopes = existing_info.scope

        if user_settings_values:
            aux_values = Values.from_list(user_settings_values)
            settings.values = aux_values

        if user_options_values is not None:  # Install will pass an empty list []
            # Install OVERWRITES options, existing options in CONANINFO are not taken
            # into account, just those from CONANFILE + user command line
            options = OptionsValues.from_list(user_options_values)

        if scopes:
            conaninfo_scopes.update_scope(scopes)

        self._current_scopes = conaninfo_scopes
        return ConanFileLoader(self._runner, settings, package_settings=package_settings,
                               options=options, scopes=conaninfo_scopes,
                               env=env, package_env=package_env)

    def export(self, user, conan_file_path, keep_source=False):
        """ Export the conans
        param conanfile_path: the original source directory of the user containing a
                           conanfile.py
        param user: user under this package will be exported
        param channel: string (stable, testing,...)
        """
        assert conan_file_path
        logger.debug("Exporting %s" % conan_file_path)
        user_name, channel = get_user_channel(user)
        conan_file = self._loader().load_class(os.path.join(conan_file_path, CONANFILE))
        for field in ["url", "license", "description"]:
            field_value = getattr(conan_file, field, None)
            if not field_value:
                self._user_io.out.warn("Conanfile doesn't have '%s'.\n"
                                       "It is recommended to add it as attribute" % field)

        conan_ref = ConanFileReference(conan_file.name, conan_file.version, user_name, channel)
        conan_ref_str = str(conan_ref)
        # Maybe a platform check could be added, but depends on disk partition
        refs = self._search_manager.search(conan_ref_str, ignorecase=True)
        if refs and conan_ref not in refs:
            raise ConanException("Cannot export package with same name but different case\n"
                                 "You exported '%s' but already existing '%s'"
                                 % (conan_ref_str, " ".join(str(s) for s in refs)))
        output = ScopedOutput(str(conan_ref), self._user_io.out)
        export_conanfile(output, self._client_cache, conan_file.exports, conan_file_path,
                         conan_ref, conan_file.short_paths, keep_source)

    def download(self, reference, package_ids, remote=None):
        """ Download conanfile and specified packages to local repository
        @param reference: ConanFileReference
        @param package_ids: Package ids or empty for download all
        @param remote: install only from that remote
        """
        assert(isinstance(reference, ConanFileReference))
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote)

        package = remote_proxy.search(reference, None)
        if not package:  # Search the reference first, and raise if it doesn't exist
            raise ConanException("'%s' not found in remote" % str(reference))

        if package_ids:
            remote_proxy.download_packages(reference, package_ids)
        else:
            packages_props = remote_proxy.search_packages(reference, None)
            if not packages_props:
                output = ScopedOutput(str(reference), self._user_io.out)
                output.warn("No remote binary packages found in remote")
            else:
                remote_proxy.download_packages(reference, list(packages_props.keys()))

    def _get_graph(self, reference, current_path, remote, options, settings, filename, update,
                   check_updates, manifest_manager, scopes, package_settings, env, package_env):

        loader = self._loader(current_path, settings, package_settings, options, scopes, env, package_env)
        # Not check for updates for info command, it'll be checked when dep graph is built

        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote,
                                  update=update, check_updates=check_updates,
                                  manifest_manager=manifest_manager)

        if isinstance(reference, ConanFileReference):
            project_reference = None
            conanfile = loader.load_virtual(reference, current_path)
            is_txt = True
        else:
            conanfile_path = reference
            project_reference = "PROJECT"
            output = ScopedOutput(project_reference, self._user_io.out)
            try:
                if filename and filename.endswith(".txt"):
                    raise NotFoundException("")
                conan_file_path = os.path.join(conanfile_path, filename or CONANFILE)
                conanfile = loader.load_conan(conan_file_path, output, consumer=True)
                is_txt = False
                if conanfile.name is not None and conanfile.version is not None:
                    project_reference = "%s/%s@" % (conanfile.name, conanfile.version)
                    project_reference += "PROJECT"
            except NotFoundException:  # Load requirements.txt
                conan_path = os.path.join(conanfile_path, filename or CONANFILE_TXT)
                conanfile = loader.load_conan_txt(conan_path, output)
                is_txt = True
        # build deps graph and install it
        local_search = None if update else self._search_manager
        resolver = RequireResolver(self._user_io.out, local_search, remote_proxy)
        builder = DepsBuilder(remote_proxy, self._user_io.out, loader, resolver)
        deps_graph = builder.load(None, conanfile)
        # These lines are so the conaninfo stores the correct complete info
        if is_txt:
            conanfile.info.settings = loader._settings.values
        conanfile.info.full_settings = loader._settings.values
        conanfile.info.scope = self._current_scopes
        conanfile.cpp_info = CppInfo(current_path)
        conanfile.env_info = EnvInfo(current_path)
        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        return (builder, deps_graph, project_reference, registry, conanfile,
                remote_proxy, loader)

    def info(self, reference, current_path, remote=None, options=None, settings=None,
             info=None, filename=None, update=False, check_updates=False, scopes=None,
             build_order=None, package_settings=None):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param current_path: where the output files will be saved
        @param remote: install only from that remote
        @param options: list of tuples: [(optionname, optionvalue), (optionname, optionvalue)...]
        @param settings: list of tuples: [(settingname, settingvalue), (settingname, value)...]
        @param package_settings: dict name=> settings: {"zlib": [(settingname, settingvalue), ...]}
        """
        objects = self._get_graph(reference, current_path, remote, options, settings, filename,
                                  update, check_updates, None, scopes, package_settings, None, None)
        (builder, deps_graph, project_reference, registry, _, _, _) = objects

        if build_order:
            result = deps_graph.build_order(build_order)
            self._user_io.out.info(", ".join(str(s) for s in result))
            return
        if check_updates:
            graph_updates_info = builder.get_graph_updates_info(deps_graph)
        else:
            graph_updates_info = {}
        Printer(self._user_io.out).print_info(deps_graph, project_reference,
                                              info, registry, graph_updates_info,
                                              remote)

    def read_profile(self, profile_name, cwd):
        if not profile_name:
            return None

        if os.path.isabs(profile_name):
            profile_path = profile_name
            folder = os.path.dirname(profile_name)
        elif profile_name.startswith("."):  # relative path name
            profile_path = os.path.abspath(os.path.join(cwd, profile_name))
            folder = os.path.dirname(profile_path)
        else:
            folder = self._client_cache.profiles_path
            profile_path = self._client_cache.profile_path(profile_name)

        try:
            text = load(profile_path)
        except Exception:
            if os.path.exists(folder):
                profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
            else:
                profiles = []
            current_profiles = ", ".join(profiles) or "[]"
            raise ConanException("Specified profile '%s' doesn't exist.\nExisting profiles: "
                                 "%s" % (profile_name, current_profiles))

        try:
            return Profile.loads(text)
        except ConanException as exc:
            raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))

    def install(self, reference, current_path, remote=None, options=None, settings=None,
                build_mode=False, filename=None, update=False, check_updates=False,
                manifest_folder=None, manifest_verify=False, manifest_interactive=False,
                scopes=None, generators=None, profile_name=None, package_settings=None,
                env=None, package_env=None, no_imports=False):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param current_path: where the output files will be saved
        @param remote: install only from that remote
        @param options: list of tuples: [(optionname, optionvalue), (optionname, optionvalue)...]
        @param settings: list of tuples: [(settingname, settingvalue), (settingname, value)...]
        @param package_settings: dict name=> settings: {"zlib": [(settingname, settingvalue), ...]}
        @param profile: name of the profile to use
        @param env: list of tuples for environment vars: [(var, value), (var2, value2)...]
        @param package_env: package dict of list of tuples: {"package_name": [(var, value), (var2, value2)...]}
        """
        generators = generators or []

        if manifest_folder:
            manifest_manager = ManifestManager(manifest_folder, user_io=self._user_io,
                                               client_cache=self._client_cache,
                                               verify=manifest_verify,
                                               interactive=manifest_interactive)
        else:
            manifest_manager = None

        profile = self.read_profile(profile_name, current_path)

        # Mix Settings, Env vars and scopes between profile and command line
        if profile:
            profile.update_settings(settings)
            profile.update_package_settings(package_settings)
            settings = profile.settings
            package_settings = profile.package_settings

            profile.update_env(env)
            profile.update_packages_env(package_env)
            env = profile.env
            package_env = profile.package_env

            profile.update_scopes(scopes)
            scopes = profile.scopes

        objects = self._get_graph(reference, current_path, remote, options, settings, filename,
                                  update, check_updates, manifest_manager, scopes, package_settings,
                                  env, package_env)
        (_, deps_graph, _, registry, conanfile, remote_proxy, loader) = objects

        Printer(self._user_io.out).print_graph(deps_graph, registry)
        # Warn if os doesn't match
        try:
            if detected_os() != loader._settings.os:
                message = '''You are building this package with settings.os='%s' on a '%s' system.
If this is your intention, you can ignore this message.
If not:
     - Check the passed settings (-s)
     - Check your global settings in ~/.conan/conan.conf
     - Remove conaninfo.txt to avoid bad cached settings
''' % (loader._settings.os, detected_os())
                self._user_io.out.warn(message)
        except ConanException:  # Setting os doesn't exist
            pass

        installer = ConanInstaller(self._client_cache, self._user_io, remote_proxy)
        installer.install(deps_graph, build_mode)

        prefix = "PROJECT" if not isinstance(reference, ConanFileReference) else str(reference)
        output = ScopedOutput(prefix, self._user_io.out)

        # Write generators
        tmp = list(conanfile.generators)  # Add the command line specified generators
        tmp.extend(generators)
        conanfile.generators = tmp
        write_generators(conanfile, current_path, output)

        if not isinstance(reference, ConanFileReference):
            content = normalize(conanfile.info.dumps())
            save(os.path.join(current_path, CONANINFO), content)
            output.info("Generated %s" % CONANINFO)
            if not no_imports:
                run_imports(conanfile, current_path, output)

        if manifest_manager:
            manifest_manager.print_log()

    def _load_info_file(self, current_path, conanfile, output, info_file, error=False):
        if info_file == BUILD_INFO:
            class_, attr, gen = DepsCppInfo, "deps_cpp_info", "txt"
        else:
            class_, attr, gen = DepsEnvInfo, "deps_env_info", "env"
        info_file_path = os.path.join(current_path, info_file)
        try:
            deps_info = class_.loads(load(info_file_path))
            setattr(conanfile, attr, deps_info)
        except IOError:
            error_msg = ("%s file not found in %s\nIt is %s for this command\n"
                         "You can generate it using 'conan install -g %s'"
                         % (info_file, current_path, "required" if error else "recommended", gen))
            if not error:
                output.warn(error_msg)
            else:
                raise ConanException(error_msg)
        except ConanException:
            raise ConanException("Parse error in '%s' file in %s" % (info_file, current_path))

    def _load_deps_info(self, current_path, conanfile, output, load_env=True, error=False):
        self._load_info_file(current_path, conanfile, output, BUILD_INFO, error=error)
        if load_env:
            self._load_info_file(current_path, conanfile, output, CONANENV, error=error)

    def source(self, current_path, reference, force):
        if not isinstance(reference, ConanFileReference):
            output = ScopedOutput("PROJECT", self._user_io.out)
            conan_file_path = os.path.join(reference, CONANFILE)
            conanfile = self._loader().load_conan(conan_file_path, output, consumer=True)
            self._load_deps_info(current_path, conanfile, output)
            export_folder = reference
            config_source_local(export_folder, current_path, conanfile, output)
        else:
            output = ScopedOutput(str(reference), self._user_io.out)
            conan_file_path = self._client_cache.conanfile(reference)
            conanfile = self._loader().load_conan(conan_file_path, output, reference=reference)
            self._load_deps_info(current_path, conanfile, output)
            src_folder = self._client_cache.source(reference, conanfile.short_paths)
            export_folder = self._client_cache.export(reference)
            config_source(export_folder, src_folder, conanfile, output, force)

    def imports_undo(self, current_path):
        undo_imports(current_path, self._user_io.out)

    def imports(self, current_path, reference, conan_file_path, dest_folder):
        if not isinstance(reference, ConanFileReference):
            output = ScopedOutput("PROJECT", self._user_io.out)
            if not conan_file_path:
                conan_file_path = os.path.join(reference, CONANFILE)
                if not os.path.exists(conan_file_path):
                    conan_file_path = os.path.join(reference, CONANFILE_TXT)

            if conan_file_path.endswith(".txt"):
                conanfile = self._loader().load_conan_txt(conan_file_path, output)
            else:
                conanfile = self._loader().load_conan(conan_file_path, output, consumer=True)
        else:
            output = ScopedOutput(str(reference), self._user_io.out)
            conan_file_path = self._client_cache.conanfile(reference)
            conanfile = self._loader().load_conan(conan_file_path, output, reference=reference)

        self._load_deps_info(current_path, conanfile, output, load_env=False, error=True)
        run_imports(conanfile, dest_folder or current_path, output)

    def local_package(self, current_path, build_folder):
        if current_path == build_folder:
            raise ConanException("Cannot 'conan package' to the build folder. "
                                 "Please move to another folder and try again")
        output = ScopedOutput("PROJECT", self._user_io.out)
        conan_file_path = os.path.join(build_folder, CONANFILE)
        conanfile = self._loader().load_conan(conan_file_path, output, consumer=True)
        self._load_deps_info(build_folder, conanfile, output)
        packager.create_package(conanfile, build_folder, current_path, output, local=True)

    def package(self, reference, package_id):
        # Package paths
        conan_file_path = self._client_cache.conanfile(reference)
        if not os.path.exists(conan_file_path):
            raise ConanException("Package recipe '%s' does not exist" % str(reference))

        if not package_id:
            packages = [PackageReference(reference, packid)
                        for packid in self._client_cache.conan_builds(reference)]
            if not packages:
                raise NotFoundException("%s: Package recipe has not been built locally\n"
                                        "Please read the 'conan package' command help\n"
                                        "Use 'conan install' or 'conan test_package' to build and "
                                        "create binaries" % str(reference))
        else:
            packages = [PackageReference(reference, package_id)]

        for package_reference in packages:
            build_folder = self._client_cache.build(package_reference, short_paths=None)
            if not os.path.exists(build_folder):
                raise NotFoundException("%s: Package binary '%s' folder doesn't exist\n"
                                        "Please read the 'conan package' command help\n"
                                        "Use 'conan install' or 'conan test_package' to build and "
                                        "create binaries"
                                        % (str(reference), package_reference.package_id))
            # The package already exist, we can use short_paths if they were defined
            package_folder = self._client_cache.package(package_reference, short_paths=None)
            # Will read current conaninfo with specified options and load conanfile with them
            output = ScopedOutput(str(reference), self._user_io.out)
            output.info("Re-packaging %s" % package_reference.package_id)
            loader = self._loader(build_folder)
            conanfile = loader.load_conan(conan_file_path, self._user_io.out,
                                          reference=package_reference.conan)
            self._load_deps_info(build_folder, conanfile, output)
            rmdir(package_folder)
            packager.create_package(conanfile, build_folder, package_folder, output)

    def build(self, conanfile_path, current_path, test=False, filename=None, profile_name=None,
              env=None, package_env=None):
        """ Call to build() method saved on the conanfile.py
        param conanfile_path: the original source directory of the user containing a
                            conanfile.py
        """
        logger.debug("Building in %s" % current_path)
        logger.debug("Conanfile in %s" % conanfile_path)

        if filename and filename.endswith(".txt"):
            raise ConanException("A conanfile.py is needed to call 'conan build'")

        conanfile_file = os.path.join(conanfile_path, filename or CONANFILE)

        try:
            # Append env_vars to execution environment and clear when block code ends
            profile = self.read_profile(profile_name, current_path)
            output = ScopedOutput("Project", self._user_io.out)
            if profile:
                profile.update_env(env)
                profile.update_packages_env(package_env)

                env = profile.env
                package_env = profile.package_env

            env = profile.env if profile else None
            package_env = profile.package_env if profile else None
            loader = self._loader(current_path, env=env, package_env=package_env)
            conan_file = loader.load_conan(conanfile_file, output, consumer=True)
        except NotFoundException:
            # TODO: Auto generate conanfile from requirements file
            raise ConanException("'%s' file is needed for build.\n"
                                 "Create a '%s' and move manually the "
                                 "requirements and generators from '%s' file"
                                 % (CONANFILE, CONANFILE, CONANFILE_TXT))
        try:
            self._load_deps_info(current_path, conan_file, output)

            os.chdir(current_path)
            conan_file._conanfile_directory = conanfile_path
            with environment_append(conan_file.env):
                conan_file.build()

            if test:
                conan_file.test()
        except ConanException:
            raise  # Raise but not let to reach the Exception except (not print traceback)
        except Exception:
            import traceback
            trace = traceback.format_exc().split('\n')
            raise ConanException("Unable to build it successfully\n%s" % '\n'.join(trace[3:]))

    def upload(self, conan_reference, package_id=None, remote=None, all_packages=None,
               force=False):

        t1 = time.time()
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote)
        uploader = ConanUploader(self._client_cache, self._user_io, remote_proxy)

        # Load conanfile to check if the build policy is set to always
        try:
            conanfile_path = self._client_cache.conanfile(conan_reference)
            conan_file = self._loader().load_class(conanfile_path)
        except NotFoundException:
            raise NotFoundException("There is no local conanfile exported as %s"
                                    % str(conan_reference))

        # Can't use build_policy_always here because it's not loaded (only load_class)
        if conan_file.build_policy == "always" and (all_packages or package_id):
            raise ConanException("Conanfile has build_policy='always', "
                                 "no packages can be uploaded")

        if package_id:  # Upload package
            uploader.upload_package(PackageReference(conan_reference, package_id))
        else:  # Upload conans
            uploader.upload_conan(conan_reference, all_packages=all_packages, force=force)

        logger.debug("====> Time manager upload: %f" % (time.time() - t1))

    def search(self, pattern_or_reference=None, remote=None, ignorecase=True, packages_query=None):
        """ Print the single information saved in conan.vars about all the packages
            or the packages which match with a pattern

            Attributes:
                pattern = string to match packages
                remote = search on another origin to get packages info
                packages_pattern = String query with binary
                                   packages properties: "arch=x86 AND os=Windows"
        """
        printer = Printer(self._user_io.out)

        if remote:
            remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager,
                                      remote)
            adapter = remote_proxy
        else:
            adapter = self._search_manager
        if isinstance(pattern_or_reference, ConanFileReference):
            packages_props = adapter.search_packages(pattern_or_reference, packages_query)
            ordered_packages = OrderedDict(sorted(packages_props.items()))
            try:
                recipe_hash = self._client_cache.load_manifest(pattern_or_reference).summary_hash
            except IOError:  # It could not exist in local
                recipe_hash = None
            printer.print_search_packages(ordered_packages, pattern_or_reference,
                                          recipe_hash, packages_query)
        else:
            references = adapter.search(pattern_or_reference, ignorecase)
            printer.print_search_recipes(references, pattern_or_reference)

    def copy(self, reference, package_ids, username, channel, force=False):
        """ Copy or move conanfile (exported) and packages to another user and or channel
        @param reference: ConanFileReference containing the packages to be moved
        @param package_ids: list of ids or [] for all list
        @param username: Destination username
        @param channel: Destination channel
        @param remote: install only from that remote
        """
        output = ScopedOutput(str(reference), self._user_io.out)
        conan_file_path = self._client_cache.conanfile(reference)
        conanfile = self._loader().load_conan(conan_file_path, output)
        copier = PackageCopier(self._client_cache, self._user_io, conanfile.short_paths)
        if not package_ids:
            packages = self._client_cache.packages(reference)
            if os.path.exists(packages):
                package_ids = os.listdir(packages)
            else:
                package_ids = []
        copier.copy(reference, package_ids, username, channel, force)

    def remove(self, pattern, src=False, build_ids=None, package_ids_filter=None, force=False,
               remote=None):
        """ Remove conans and/or packages
        @param pattern: string to match packages
        @param package_ids: list of ids or [] for all list
        @param remote: search on another origin to get packages info
        @param force: if True, it will be deleted without requesting anything
        """
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote)
        remover = ConanRemover(self._client_cache, self._search_manager, self._user_io,
                               remote_proxy)
        remover.remove(pattern, src, build_ids, package_ids_filter, force=force)

    def user(self, remote=None, name=None, password=None):
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote)
        return remote_proxy.authenticate(name, password)
