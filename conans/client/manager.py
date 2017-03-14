import os
import time
from collections import OrderedDict, Counter

from conans.client import packager
from conans.client.client_cache import ClientCache
from conans.client.deps_builder import DepsGraphBuilder
from conans.client.detect import detected_os
from conans.client.export import export_conanfile
from conans.client.generators import write_generators
from conans.client.grapher import ConanGrapher, ConanHTMLGrapher
from conans.client.importer import run_imports, undo_imports
from conans.client.installer import ConanInstaller
from conans.client.loader import ConanFileLoader
from conans.client.manifest_manager import ManifestManager
from conans.client.output import ScopedOutput, Color
from conans.client.package_copier import PackageCopier
from conans.client.printer import Printer
from conans.client.proxy import ConanProxy
from conans.client.remote_registry import RemoteRegistry
from conans.client.remover import ConanRemover
from conans.client.require_resolver import RequireResolver
from conans.client.source import config_source, config_source_local
from conans.client.uploader import ConanUploader
from conans.client.userio import UserIO
from conans.errors import NotFoundException, ConanException
from conans.model.build_info import DepsCppInfo, CppInfo
from conans.model.env_info import EnvInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import (CONANFILE, CONANINFO, CONANFILE_TXT, BUILD_INFO)
from conans.tools import environment_append
from conans.util.files import save, load, rmdir, normalize, mkdir
from conans.util.log import logger
from conans.model.profile import Profile
from conans.model.info import ConanInfo


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

    def _loader(self, conan_info_path=None, profile=None):
        # The disk settings definition, already including the default disk values
        settings = self._client_cache.settings
        mixed_profile = Profile()
        if profile is None:
            if conan_info_path and os.path.exists(conan_info_path):
                existing_info = ConanInfo.load_file(conan_info_path)
                settings.values = existing_info.full_settings
                mixed_profile.options = existing_info.full_options
                mixed_profile.scopes = existing_info.scope
                mixed_profile.env_values = existing_info.env_values
        else:
            mixed_profile.env_values.update(profile.env_values)
            settings.values = profile.settings_values
            if profile.scopes:
                mixed_profile.scopes.update_scope(profile.scopes)
            mixed_profile.options.update(profile.options)
            for pkg, pkg_settings in profile.package_settings.items():
                mixed_profile.package_settings[pkg].update(pkg_settings)

        self._current_scopes = mixed_profile.scopes
        return ConanFileLoader(self._runner, settings=settings,
                               package_settings=mixed_profile.package_settings_values,
                               options=mixed_profile.options, scopes=mixed_profile.scopes,
                               env_values=mixed_profile.env_values)

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
        if getattr(conan_file, "conan_info", None):
            self._user_io.out.warn("conan_info() method is deprecated, use package_id() instead")

        conan_ref = ConanFileReference(conan_file.name, conan_file.version, user_name, channel)
        conan_ref_str = str(conan_ref)
        # Maybe a platform check could be added, but depends on disk partition
        refs = self._search_manager.search(conan_ref_str, ignorecase=True)
        if refs and conan_ref not in refs:
            raise ConanException("Cannot export package with same name but different case\n"
                                 "You exported '%s' but already existing '%s'"
                                 % (conan_ref_str, " ".join(str(s) for s in refs)))
        output = ScopedOutput(str(conan_ref), self._user_io.out)
        export_conanfile(output, self._client_cache, conan_file, conan_file_path,
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

    def _get_graph(self, reference, current_path, profile, remote, filename, update,
                   check_updates, manifest_manager):
        conan_info_path = os.path.join(current_path, CONANINFO)
        loader = self._loader(conan_info_path, profile)
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
            except NotFoundException:  # Load conanfile.txt
                conan_path = os.path.join(conanfile_path, filename or CONANFILE_TXT)
                conanfile = loader.load_conan_txt(conan_path, output)
                is_txt = True
        # build deps graph and install it
        local_search = None if update else self._search_manager
        resolver = RequireResolver(self._user_io.out, local_search, remote_proxy)
        builder = DepsGraphBuilder(remote_proxy, self._user_io.out, loader, resolver)
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

    def info(self, reference, current_path, profile, remote=None,
             info=None, filename=None, update=False, check_updates=False,
             build_order=None, build_mode=None, graph_filename=None, package_filter=None,
             show_paths=False):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param current_path: where the output files will be saved
        @param remote: install only from that remote
        @param options: list of tuples: [(optionname, optionvalue), (optionname, optionvalue)...]
        @param settings: list of tuples: [(settingname, settingvalue), (settingname, value)...]
        @param package_settings: dict name=> settings: {"zlib": [(settingname, settingvalue), ...]}
        """

        objects = self._get_graph(reference, current_path, profile, remote, filename,
                                  update, check_updates, None)

        (builder, deps_graph, project_reference, registry, _, remote_proxy, _) = objects

        if build_order:
            result = deps_graph.build_order(build_order)
            self._user_io.out.info(", ".join(str(s) for s in result))
            return

        if build_mode is not None:
            installer = ConanInstaller(self._client_cache, self._user_io, remote_proxy)
            nodes = installer.nodes_to_build(deps_graph, build_mode)
            counter = Counter(ref.conan.name for ref, _ in nodes)
            self._user_io.out.info(", ".join((str(ref)
                                              if counter[ref.conan.name] > 1 else str(ref.conan))
                                             for ref, _ in nodes))
            return

        if check_updates:
            graph_updates_info = builder.get_graph_updates_info(deps_graph)
        else:
            graph_updates_info = {}

        def read_dates(deps_graph):
            ret = {}
            for ref, _ in sorted(deps_graph.nodes):
                if ref:
                    manifest = self._client_cache.load_manifest(ref)
                    ret[ref] = manifest.time_str
            return ret

        if graph_filename:
            if graph_filename.endswith(".html"):
                grapher = ConanHTMLGrapher(project_reference, deps_graph)
            else:
                grapher = ConanGrapher(project_reference, deps_graph)
            grapher.graph_file(graph_filename)
        else:
            Printer(self._user_io.out).print_info(deps_graph, project_reference,
                                                  info, registry, graph_updates_info,
                                                  remote, read_dates(deps_graph),
                                                  self._client_cache, package_filter, show_paths)

    def install(self, reference, current_path, profile, remote=None,
                build_mode=None, filename=None, update=False, check_updates=False,
                manifest_folder=None, manifest_verify=False, manifest_interactive=False,
                generators=None, no_imports=False):
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

        objects = self._get_graph(reference, current_path, profile, remote, filename,
                                  update, check_updates, manifest_manager)
        (_, deps_graph, _, registry, conanfile, remote_proxy, loader) = objects

        Printer(self._user_io.out).print_graph(deps_graph, registry)

        try:
            if detected_os() != loader._settings.os:
                message = "Cross-platform from '%s' to '%s'" % (detected_os(), loader._settings.os)
                self._user_io.out.writeln(message, Color.BRIGHT_MAGENTA)
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
            installer.call_system_requirements(conanfile, output)

        if manifest_manager:
            manifest_manager.print_log()

    def source(self, current_path, reference, force):
        conan_info_path = os.path.join(current_path, CONANINFO)
        if not isinstance(reference, ConanFileReference):
            output = ScopedOutput("PROJECT", self._user_io.out)
            conan_file_path = os.path.join(reference, CONANFILE)
            conanfile = self._loader(conan_info_path).load_conan(conan_file_path, output,
                                                                 consumer=True)
            _load_info_file(current_path, conanfile, output)
            export_folder = reference
            config_source_local(export_folder, current_path, conanfile, output)
        else:
            output = ScopedOutput(str(reference), self._user_io.out)
            conan_file_path = self._client_cache.conanfile(reference)
            conanfile = self._loader(conan_info_path).load_conan(conan_file_path, output,
                                                                 reference=reference)
            _load_info_file(current_path, conanfile, output)
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

        _load_info_file(current_path, conanfile, output, error=True)
        if dest_folder:
            if not os.path.isabs(dest_folder):
                dest_folder = os.path.normpath(os.path.join(current_path, dest_folder))
            mkdir(dest_folder)
        else:
            dest_folder = current_path
        run_imports(conanfile, dest_folder, output)

    def local_package(self, current_path, build_folder):
        if current_path == build_folder:
            raise ConanException("Cannot 'conan package' to the build folder. "
                                 "Please move to another folder and try again")
        output = ScopedOutput("PROJECT", self._user_io.out)
        conan_file_path = os.path.join(build_folder, CONANFILE)
        conanfile = self._loader().load_conan(conan_file_path, output, consumer=True)
        _load_info_file(build_folder, conanfile, output)
        packager.create_package(conanfile, build_folder, current_path, output, local=True)

    def package(self, reference, package_id):
        # Package paths
        conan_file_path = self._client_cache.conanfile(reference)
        if not os.path.exists(conan_file_path):
            raise ConanException("Package recipe '%s' does not exist" % str(reference))

        loader = self._loader()
        conanfile = loader.load_conan(conan_file_path, self._user_io.out, reference=reference)
        if hasattr(conanfile, "build_id"):
            raise ConanException("package command does not support recipes with 'build_id'\n"
                                 "To repackage them use 'conan install'")

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
            conan_info_path = os.path.join(build_folder, CONANINFO)
            loader = self._loader(conan_info_path)

            conanfile = loader.load_conan(conan_file_path, self._user_io.out, reference=reference)
            _load_info_file(build_folder, conanfile, output)
            rmdir(package_folder)
            with environment_append(conanfile.env):
                packager.create_package(conanfile, build_folder, package_folder, output)

    def build(self, conanfile_path, current_path, test=False, filename=None):
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
            output = ScopedOutput("Project", self._user_io.out)
            conan_info_path = os.path.join(current_path, CONANINFO)
            loader = self._loader(conan_info_path)
            conan_file = loader.load_conan(conanfile_file, output, consumer=True)
        except NotFoundException:
            # TODO: Auto generate conanfile from requirements file
            raise ConanException("'%s' file is needed for build.\n"
                                 "Create a '%s' and move manually the "
                                 "requirements and generators from '%s' file"
                                 % (CONANFILE, CONANFILE, CONANFILE_TXT))
        try:
            _load_info_file(current_path, conan_file, output)
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

    def upload(self, conan_reference_or_pattern, package_id=None, remote=None, all_packages=None,
               force=False, confirm=False, retry=0, retry_wait=0, skip_upload=False):
        """If package_id is provided, conan_reference_or_pattern is a ConanFileReference"""
        t1 = time.time()
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager,
                                  remote)
        uploader = ConanUploader(self._client_cache, self._user_io, remote_proxy,
                                 self._search_manager, self._loader())

        if package_id:  # Upload package
            ref = ConanFileReference.loads(conan_reference_or_pattern)
            uploader.check_reference(ref)
            uploader.upload_package(PackageReference(ref, package_id), retry=retry,
                                    retry_wait=retry_wait, skip_upload=skip_upload)
        else:  # Upload conans
            uploader.upload(conan_reference_or_pattern, all_packages=all_packages,
                            force=force, confirm=confirm,
                            retry=retry, retry_wait=retry_wait, skip_upload=skip_upload)

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
        # It is necessary to make sure the sources are complete before proceeding
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, None)
        remote_proxy.complete_recipe_sources(reference)

        # Now we can actually copy
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
               remote=None, packages_query=None):
        """ Remove conans and/or packages
        @param pattern: string to match packages
        @param src: Remove src folder
        @param package_ids_filter: list of ids or [] for all list
        @param build_ids: list of ids or [] for all list
        @param remote: search on another origin to get packages info
        @param force: if True, it will be deleted without requesting anything
        @param packages_query: Only if src is a reference. Query settings and options
        """
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote)
        remover = ConanRemover(self._client_cache, self._search_manager, self._user_io,
                               remote_proxy)
        remover.remove(pattern, src, build_ids, package_ids_filter, force=force, packages_query=packages_query)

    def user(self, remote=None, name=None, password=None):
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote)
        return remote_proxy.authenticate(name, password)


def _load_info_file(current_path, conanfile, output, error=False):
    class_, attr, gen = DepsCppInfo, "deps_cpp_info", "txt"

    info_file_path = os.path.join(current_path, BUILD_INFO)
    try:
        deps_info = class_.loads(load(info_file_path))
        setattr(conanfile, attr, deps_info)
    except IOError:
        error_msg = ("%s file not found in %s\nIt is %s for this command\n"
                     "You can generate it using 'conan install -g %s'"
                     % (BUILD_INFO, current_path, "required" if error else "recommended", gen))
        if not error:
            output.warn(error_msg)
        else:
            raise ConanException(error_msg)
    except ConanException:
        raise ConanException("Parse error in '%s' file in %s" % (BUILD_INFO, current_path))
