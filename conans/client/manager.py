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
from conans.client.importer import FileImporter
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
from conans.client.file_copier import report_copied_files
from conans.model.scope import Scopes
from conans.client.client_cache import ClientCache
from conans.client.source import config_source, config_source_local
from conans.client.manifest_manager import ManifestManager
from conans.model.env_info import EnvInfo, DepsEnvInfo
from conans.tools import environment_append


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

    def _loader(self, current_path=None, user_settings_values=None, user_options_values=None,
                scopes=None):

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
        return ConanFileLoader(self._runner, settings, options=options, scopes=conaninfo_scopes)

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
        url = getattr(conan_file, "url", None)
        license_ = getattr(conan_file, "license", None)
        if not url:
            self._user_io.out.warn("Conanfile doesn't have 'url'.\n"
                                   "It is recommended to add your repo URL as attribute")
        if not license_:
            self._user_io.out.warn("Conanfile doesn't have a 'license'.\n"
                                   "It is recommended to add the package license as attribute")

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

        if package_ids:
            remote_proxy.download_packages(reference, package_ids)
        else:  # Not specified packages, download all
            packages_props = remote_proxy.search_packages(reference, None)
            if not packages_props:  # No filter by properties
                raise ConanException("'%s' not found in remote" % str(reference))

            remote_proxy.download_packages(reference, list(packages_props.keys()))

    def _get_graph(self, reference, current_path, remote, options, settings, filename, update,
                   check_updates, manifest_manager, scopes):

        loader = self._loader(current_path, settings, options, scopes)
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
        builder = DepsBuilder(remote_proxy, self._user_io.out, loader)
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
             build_order=None):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param current_path: where the output files will be saved
        @param remote: install only from that remote
        @param options: list of tuples: [(optionname, optionvalue), (optionname, optionvalue)...]
        @param settings: list of tuples: [(settingname, settingvalue), (settingname, value)...]
        """
        objects = self._get_graph(reference, current_path, remote, options, settings, filename,
                                  update, check_updates, None, scopes)
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

    def _read_profile(self, profile_name):
        if profile_name:
            try:
                profile = self._client_cache.load_profile(profile_name)
                return profile
            except ConanException as exc:
                raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))

        return None

    def _mix_settings_and_profile(self, settings, profile):
        '''Mix the specified settings with the specified profile.
        Specified settings are prioritized to profile'''
        if profile:
            profile.update_settings(dict(settings))
            return profile.settings.items()
        return settings

    def _mix_scopes_and_profile(self, scopes, profile):
        if profile:
            profile.update_scopes(scopes)
            return profile.scopes
        return scopes

    def _read_profile_env_vars(self, profile):
        if profile:
            return profile.env
        return {}

    def install(self, reference, current_path, remote=None, options=None, settings=None,
                build_mode=False, filename=None, update=False, check_updates=False,
                manifest_folder=None, manifest_verify=False, manifest_interactive=False,
                scopes=None, generators=None, profile_name=None):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param current_path: where the output files will be saved
        @param remote: install only from that remote
        @param options: list of tuples: [(optionname, optionvalue), (optionname, optionvalue)...]
        @param settings: list of tuples: [(settingname, settingvalue), (settingname, value)...]
        @param profile: name of the profile to use
        """
        generators = generators or []

        if manifest_folder:
            manifest_manager = ManifestManager(manifest_folder, user_io=self._user_io,
                                               client_cache=self._client_cache,
                                               verify=manifest_verify,
                                               interactive=manifest_interactive)
        else:
            manifest_manager = None

        profile = self._read_profile(profile_name)
        settings = self._mix_settings_and_profile(settings, profile)
        scopes = self._mix_scopes_and_profile(scopes, profile)
        env_vars = self._read_profile_env_vars(profile)

        objects = self._get_graph(reference, current_path, remote, options, settings, filename,
                                  update, check_updates, manifest_manager, scopes)
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

        # Append env_vars to execution environment and clear when block code ends
        with environment_append(env_vars):
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
            local_installer = FileImporter(deps_graph, self._client_cache, current_path)
            conanfile.copy = local_installer
            conanfile.imports()
            copied_files = local_installer.execute()
            import_output = ScopedOutput("%s imports()" % output.scope, output)
            report_copied_files(copied_files, import_output)

        if manifest_manager:
            manifest_manager.print_log()

    def _load_deps_info(self, current_path, conanfile, output):
        build_info_file = os.path.join(current_path, BUILD_INFO)
        if os.path.exists(build_info_file):
            try:
                deps_cpp_info = DepsCppInfo.loads(load(build_info_file))
                conanfile.deps_cpp_info = deps_cpp_info
            except:
                output.error("Parse error in '%s' file in %s" % (BUILD_INFO, current_path))
        else:
            output.warn("%s file not found in %s\nIt is recommended for source, build and package "
                        "commands\nYou can generate it using 'conan install -g env -g txt'"
                        % (BUILD_INFO, current_path))

        env_file = os.path.join(current_path, CONANENV)
        if os.path.exists(env_file):
            try:
                deps_env_info = DepsEnvInfo.loads(load(env_file))
                conanfile.deps_env_info = deps_env_info
            except:
                output.error("Parse error in '%s' file in %s" % (CONANENV, current_path))
        else:
            output.warn("%s file not found in %s\nIt is recommended for source, build and package "
                        "commands\nYou can generate it using 'conan install -g env -g txt'"
                        % (CONANENV, current_path))

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
            conanfile = self._loader().load_conan(conan_file_path, output)
            self._load_deps_info(current_path, conanfile, output)
            src_folder = self._client_cache.source(reference, conanfile.short_paths)
            export_folder = self._client_cache.export(reference)
            config_source(export_folder, src_folder, conanfile, output, force)

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
            conanfile = loader.load_conan(conan_file_path, self._user_io.out)
            self._load_deps_info(build_folder, conanfile, output)
            rmdir(package_folder)
            packager.create_package(conanfile, build_folder, package_folder, output)

    def build(self, conanfile_path, current_path, test=False, filename=None, profile_name=None):
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
            output = ScopedOutput("Project", self._user_io.out)
            conan_file = self._loader(current_path).load_conan(conanfile_file, output,
                                                               consumer=True)
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
            # Append env_vars to execution environment and clear when block code ends
            profile = self._read_profile(profile_name)
            env_vars = self._read_profile_env_vars(profile)
            with environment_append(env_vars):
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
            recipe_hash = self._client_cache.load_manifest(pattern_or_reference).summary_hash
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
