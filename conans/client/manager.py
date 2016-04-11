import os
from conans.paths import (CONANFILE, CONANINFO, CONANFILE_TXT, BUILD_INFO)
from conans.client.loader import ConanFileLoader
from conans.client.export import export_conanfile
from conans.client.deps_builder import DepsBuilder
from conans.client.userio import UserIO
from conans.client.installer import ConanInstaller
from conans.util.files import save, load, rmdir, normalize
from conans.util.log import logger
from conans.client.uploader import ConanUploader
from conans.client.printer import Printer
from conans.client.paths import ConanPaths
from conans.errors import NotFoundException, ConanException
from conans.client.generators import write_generators
from conans.client.importer import FileImporter
from conans.model.ref import ConanFileReference, PackageReference
from conans.client.remover import ConanRemover
from conans.model.info import ConanInfo
from conans.server.store.disk_adapter import DiskAdapter
from conans.server.store.file_manager import FileManager
from conans.model.values import Values
from conans.model.options import OptionsValues
import re
from conans.info import SearchInfo
from conans.model.build_info import DepsCppInfo
from conans.client import packager
from conans.client.package_copier import PackageCopier
from conans.client.output import ScopedOutput
from conans.client.proxy import ConanProxy
from conans.client.remote_registry import RemoteRegistry
from conans.client.file_copier import report_copied_files


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
    def __init__(self, paths, user_io, runner, remote_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(paths, ConanPaths)
        self._paths = paths
        self._user_io = user_io
        self._runner = runner
        self._remote_manager = remote_manager

    def _loader(self, current_path=None, user_settings_values=None, user_options_values=None):
        # The disk settings definition, already including the default disk values
        settings = self._paths.settings
        options = OptionsValues()

        if current_path:
            conan_info_path = os.path.join(current_path, CONANINFO)
            if os.path.exists(conan_info_path):
                existing_info = ConanInfo.load_file(conan_info_path)
                settings.values = existing_info.full_settings
                options = existing_info.full_options  # Take existing options from conaninfo.txt

        if user_settings_values:
            aux_values = Values.from_list(user_settings_values)
            settings.values = aux_values

        if user_options_values is not None:  # Install will pass an empty list []
            # Install OVERWRITES options, existing options in CONANINFO are not taken
            # into account, just those from CONANFILE + user command line
            options = OptionsValues.from_list(user_options_values)

        return ConanFileLoader(self._runner, settings, options=options)

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
        conan_file = self._loader().load_conan(os.path.join(conan_file_path, CONANFILE),
                                               self._user_io.out)
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
        info = self.file_manager.search(conan_ref_str, ignorecase=True)
        refs = {s for s in info.keys() if str(s).lower() == conan_ref_str.lower()}
        if refs and conan_ref not in refs:
            raise ConanException("Cannot export package with same name but different case\n"
                                 "You exported '%s' but already existing '%s'"
                                 % (conan_ref_str, " ".join(str(s) for s in refs)))
        output = ScopedOutput(str(conan_ref), self._user_io.out)
        export_conanfile(output, self._paths,
                         conan_file.exports, conan_file_path, conan_ref, keep_source)

    def download(self, reference, package_ids, remote=None):
        """ Download conanfile and specified packages to local repository
        @param reference: ConanFileReference
        @param package_ids: Package ids or empty for download all
        @param remote: install only from that remote
        """
        assert(isinstance(reference, ConanFileReference))
        remote_proxy = ConanProxy(self._paths, self._user_io, self._remote_manager, remote)

        if package_ids:
            remote_proxy.download_packages(reference, package_ids)
        else:  # Not specified packages, download all
            info = remote_proxy.search(str(reference), ignorecase=False)
            if reference not in info:
                remote = remote or self._remote_manager.default_remote
                raise ConanException("'%s' not found in remote '%s'" % (str(reference), remote))

            remote_proxy.download_packages(reference, list(info[reference].keys()))

    def install(self, reference, current_path, remote=None, options=None, settings=None,
                build_mode=False, info=None, filename=None, update=False):
        """ Fetch and build all dependencies for the given reference
        @param reference: ConanFileReference or path to user space conanfile
        @param current_path: where the output files will be saved
        @param remote: install only from that remote
        @param options: list of tuples: [(optionname, optionvalue), (optionname, optionvalue)...]
        @param settings: list of tuples: [(settingname, settingvalue), (settingname, value)...]
        """
        reference_given = True
        if not isinstance(reference, ConanFileReference):
            conanfile_path = reference
            reference_given = False
            reference = None

        loader = self._loader(current_path, settings, options)
        # Not check for updates for info command, it'll be checked when dep graph is built
        check_updates = not info
        remote_proxy = ConanProxy(self._paths, self._user_io, self._remote_manager,
                                  remote, update, check_updates)

        if reference_given:
            project_reference = None
            conanfile_path = remote_proxy.get_conanfile(reference)
            output = ScopedOutput(str(reference), self._user_io.out)
            conanfile = loader.load_conan(conanfile_path, output, consumer=True)
        else:
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
        deps_graph = builder.load(reference, conanfile)
        registry = RemoteRegistry(self._paths.registry, self._user_io.out)
        if info:
            graph_updates_info = builder.get_graph_updates_info(deps_graph)
            Printer(self._user_io.out).print_info(deps_graph, project_reference,
                                                  info, registry, graph_updates_info,
                                                  remote)
            return
        Printer(self._user_io.out).print_graph(deps_graph, registry)

        installer = ConanInstaller(self._paths, self._user_io, remote_proxy)
        installer.install(deps_graph, build_mode)

        if not reference_given:
            if is_txt:
                conanfile.info.settings = loader._settings.values
            # Just in case the current package is header only, we still store the full settings
            # for reference and compiler checks
            conanfile.info.full_settings = loader._settings.values
            content = normalize(conanfile.info.dumps())
            save(os.path.join(current_path, CONANINFO), content)
            output.info("Generated %s" % CONANINFO)
            write_generators(conanfile, current_path, output)
            local_installer = FileImporter(deps_graph, self._paths, current_path)
            conanfile.copy = local_installer
            conanfile.imports()
            copied_files = local_installer.execute()
            import_output = ScopedOutput("%s imports()" % output.scope, output)
            report_copied_files(copied_files, import_output)

    def package(self, reference, package_id, only_manifest, package_all):
        assert(isinstance(reference, ConanFileReference))

        # Package paths
        conan_file_path = self._paths.conanfile(reference)

        if package_all:
            if only_manifest:
                packages_dir = self._paths.packages(reference)
            else:
                packages_dir = self._paths.builds(reference)
            if not os.path.exists(packages_dir):
                raise NotFoundException('%s does not exist' % str(reference))
            packages = [PackageReference(reference, packid)
                        for packid in os.listdir(packages_dir)]
        else:
            packages = [PackageReference(reference, package_id)]

        for package_reference in packages:
            package_folder = self._paths.package(package_reference)
            # Will read current conaninfo with specified options and load conanfile with them
            if not only_manifest:
                self._user_io.out.info("Packaging %s" % package_reference.package_id)
                build_folder = self._paths.build(package_reference)
                loader = self._loader(build_folder)
                conanfile = loader.load_conan(conan_file_path, self._user_io.out)
                rmdir(package_folder)
                output = ScopedOutput(str(reference), self._user_io.out)
                packager.create_package(conanfile, build_folder, package_folder, output)
            else:
                self._user_io.out.info("Creating manifest for %s" % package_reference.package_id)
                if not os.path.exists(package_folder):
                    raise NotFoundException('Package %s does not exist' % str(package_reference))
                packager.generate_manifest(package_folder)

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
            build_info_file = os.path.join(current_path, BUILD_INFO)
            if os.path.exists(build_info_file):
                try:
                    deps_cpp_info = DepsCppInfo.loads(load(build_info_file))
                    conan_file.deps_cpp_info = deps_cpp_info
                except:
                    pass

            os.chdir(current_path)
            conan_file._conanfile_directory = conanfile_path
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

        remote_proxy = ConanProxy(self._paths, self._user_io, self._remote_manager, remote)
        uploader = ConanUploader(self._paths, self._user_io, remote_proxy)

        if package_id:  # Upload package
            uploader.upload_package(PackageReference(conan_reference, package_id))
        else:  # Upload conans
            uploader.upload_conan(conan_reference, all_packages=all_packages, force=force)

    def search(self, pattern=None, remote=None, ignorecase=True,
               verbose=False, extra_verbose=False, package_pattern=None):
        """ Print the single information saved in conan.vars about all the packages
            or the packages which match with a pattern

            Attributes:
                pattern = string to match packages
                remote = search on another origin to get packages info
        """
        if remote:
            remote_proxy = ConanProxy(self._paths, self._user_io, self._remote_manager, remote)
            info = remote_proxy.search(pattern, ignorecase)
        else:
            info = self.file_manager.search(pattern, ignorecase)

        filtered_info = info

        # Filter packages if package_pattern
        if package_pattern:
            try:
                # Prepare ER to be more user natural
                if ".*" not in package_pattern:
                    package_pattern = package_pattern.replace("*", ".*")

                # Compile expression
                package_pattern = re.compile(package_pattern, re.IGNORECASE)
                filtered_info = SearchInfo()
                for conan_ref, packages in sorted(info.items()):
                    filtered_packages = {pid: data for pid, data in packages.items()
                                         if package_pattern.match(pid)}
                    if filtered_packages:
                        filtered_info[conan_ref] = filtered_packages
            except Exception:  # Invalid pattern
                raise ConanException("Invalid package pattern")

        printer = Printer(self._user_io.out)
        printer.print_search(filtered_info, pattern, verbose, extra_verbose)

    @property
    def file_manager(self):
        # FIXME: Looks like a refactor, it doesnt fix here instance file_manager or
        # file_manager maybe should be injected in client and all the storage work
        # should be done there?
        disk_adapter = DiskAdapter("", self._paths.store, None)
        file_manager = FileManager(self._paths, disk_adapter)
        return file_manager

    def copy(self, reference, package_ids, username, channel, force=False):
        """ Copy or move conanfile (exported) and packages to another user and or channel
        @param reference: ConanFileReference containing the packages to be moved
        @param package_ids: list of ids or [] for all list
        @param username: Destination username
        @param channel: Destination channel
        @param remote: install only from that remote
        """
        copier = PackageCopier(self._paths, self._user_io)
        package_ids = package_ids or os.listdir(self._paths.packages(reference))
        copier.copy(reference, package_ids, username, channel, force)

    def remove(self, pattern, src=False, build_ids=None, package_ids_filter=None, force=False,
               remote=None):
        """ Remove conans and/or packages
        @param pattern: string to match packages
        @param package_ids: list of ids or [] for all list
        @param remote: search on another origin to get packages info
        @param force: if True, it will be deleted without requesting anything
        """
        remote_proxy = ConanProxy(self._paths, self._user_io, self._remote_manager, remote)
        remover = ConanRemover(self.file_manager, self._user_io, remote_proxy)
        remover.remove(pattern, src, build_ids, package_ids_filter, force=force)

    def user(self, remote=None, name=None, password=None):
        remote_proxy = ConanProxy(self._paths, self._user_io, self._remote_manager, remote)
        return remote_proxy.authenticate(name, password)
