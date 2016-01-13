import os
from conans.paths import (CONANFILE, CONANINFO, CONANFILE_TXT, BUILD_INFO)
from conans.client.loader import ConanFileLoader
from conans.client.export import export_conanfile
from conans.client.deps_builder import DepsBuilder
from conans.client.userio import UserIO
from conans.client.installer import ConanInstaller
from conans.util.files import save, load, rmdir
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
from conans.client.output import Color


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
    def __init__(self, paths, user_io, runner, remote_manager, localdb):
        assert isinstance(user_io, UserIO)
        assert isinstance(paths, ConanPaths)
        self._paths = paths
        self._user_io = user_io
        self._runner = runner
        self.remote_manager = remote_manager
        self._localdb = localdb

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
            # FIXME: CHapuza
            aux_values = Values.loads("\n".join(user_settings_values))
            settings.values = aux_values

        if user_options_values is not None:  # Install will pass an empty list []
            # Install OVERWRITES options, existing options in CONANINFO are not taken
            # into account, just those from CONANFILE + user command line
            options = OptionsValues.loads("\n".join(user_options_values))

        return ConanFileLoader(self._user_io.out, self._runner, settings, options=options)

    def export(self, user, conan_file_path):
        """ Export the conans
        param conanfile_path: the original source directory of the user containing a
                           conanfile.py
        param user: user under this package will be exported
        param channel: string (stable, testing,...)
        """
        assert conan_file_path
        logger.debug("Exporting %s" % conan_file_path)
        user_name, channel = get_user_channel(user)
        conan_file = self._loader().load_conan(os.path.join(conan_file_path, CONANFILE))
        url = getattr(conan_file, "url", None)
        license_ = getattr(conan_file, "license", None)
        if not url:
            self._user_io.out.warn("Conanfile doesn't have 'url'.\n"
                                   "It is recommended to add your repo URL as attribute")
        if not license_:
            self._user_io.out.warn("Conanfile doesn't have a 'license'.\n"
                                  "It is recommended to add the package license as attribute")

        conan_ref = ConanFileReference(conan_file.name, conan_file.version, user_name, channel)
        export_conanfile(self._user_io.out, self._paths,
                         conan_file.exports, conan_file_path, conan_ref)

    def install(self, reference, current_path, remote=None, options=None, settings=None,
                build_mode=False, info=None):
        """ Fetch and build all dependencies for the given reference
        param reference: ConanFileReference or path to user space conanfile
        param current_path: where the output files will be saved
        param remote: install only from that remote
        param options: written in JSON, e.g. {"compiler": "Visual Studio 12", ...}
        """
        if not isinstance(reference, ConanFileReference):
            conanfile_path = reference
            reference = None

        loader = self._loader(current_path, settings, options)
        installer = ConanInstaller(self._paths, self._user_io, loader, self.remote_manager, remote)

        if reference:
            conanfile = installer.retrieve_conanfile(reference, consumer=True)
        else:
            try:
                conan_file_path = os.path.join(conanfile_path, CONANFILE)
                conanfile = loader.load_conan(conan_file_path, consumer=True)
                is_txt = False
            except NotFoundException:  # Load requirements.txt
                conan_path = os.path.join(conanfile_path, CONANFILE_TXT)
                conanfile = loader.load_conan_txt(conan_path)
                is_txt = True

        # build deps graph and install it
        builder = DepsBuilder(installer, self._user_io.out)
        deps_graph = builder.load(reference, conanfile)
        if info:
            Printer(self._user_io.out).print_info(deps_graph, info)
            return
        Printer(self._user_io.out).print_graph(deps_graph)
        installer.install(deps_graph, build_mode)

        if not reference:
            if is_txt:
                conanfile.info.settings = loader._settings.values
                conanfile.info.full_settings = loader._settings.values
            save(os.path.join(current_path, CONANINFO), conanfile.info.dumps())
            self._user_io.out.info("Generated %s" % CONANINFO)
            write_generators(conanfile, current_path, self._user_io.out)
            local_installer = FileImporter(deps_graph, self._paths, current_path)
            conanfile.copy = local_installer
            conanfile.imports()
            local_installer.execute()

    def package(self, reference, package_id, only_manifest, package_all):
        assert(isinstance(reference, ConanFileReference))

        # Package paths
        conan_file_path = self._paths.conanfile(reference)

        if package_all:
            packages_dir = self._paths.packages(reference)
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
                conanfile = loader.load_conan(conan_file_path)
                rmdir(package_folder)
                packager.create_package(conanfile, build_folder, package_folder, self._user_io.out)
            else:
                self._user_io.out.info("Creating manifest for %s" % package_reference.package_id)
                if not os.path.exists(package_folder):
                    raise NotFoundException('Package %s does not exist' % str(package_reference))
                packager.generate_manifest(package_folder)

    def build(self, conanfile_path, current_path, test=False):
        """ Call to build() method saved on the conanfile.py
        param conanfile_path: the original source directory of the user containing a
                            conanfile.py
        """
        logger.debug("Building in %s" % current_path)
        logger.debug("Conanfile in %s" % conanfile_path)
        conanfile_file = os.path.join(conanfile_path, CONANFILE)

        try:
            conan_file = self._loader(current_path).load_conan(conanfile_file, consumer=True)
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

        if not remote:
            remote = self.remote_manager.default_remote  # Not iterate in remotes, just current

        uploader = ConanUploader(self._paths, self._user_io, self.remote_manager, remote)

        if package_id:  # Upload package
            uploader.upload_package(PackageReference(conan_reference, package_id))
        else:  # Upload conans
            uploader.upload_conan(conan_reference, all_packages=all_packages, force=force)

    def search(self, pattern=None, remote=None, ignorecase=True,
               verbose=False, package_pattern=None):
        """ Print the single information saved in conan.vars about all the packages
            or the packages which match with a pattern

            Attributes:
                pattern = string to match packages
                remote = search on another origin to get packages info
        """
        if remote:
            info = self.remote_manager.search(pattern, remote, ignorecase)
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
                for conan_ref, packages in sorted(info.iteritems()):
                    filtered_packages = {pid: data for pid, data in packages.iteritems()
                                         if package_pattern.match(pid)}
                    if filtered_packages:
                        filtered_info[conan_ref] = filtered_packages
            except Exception:  # Invalid pattern
                raise ConanException("Invalid package pattern")

        printer = Printer(self._user_io.out)
        printer.print_search(filtered_info, pattern, verbose)

    @property
    def file_manager(self):
        # FIXME: Looks like a refactor, it doesnt fix here instance file_manager or
        # file_manager maybe should be injected in client and all the storage work
        # should be done there?
        disk_adapter = DiskAdapter("", self._paths.store, None)
        file_manager = FileManager(self._paths, disk_adapter)
        return file_manager

    def remove(self, pattern, src=False, build_ids=None, package_ids_filter=None, force=False,
               remote=None):
        """ Remove conans and/or packages
        @param pattern: string to match packages
        @param package_ids: list of ids or [] for all list
        @param remote: search on another origin to get packages info
        @param force: if True, it will be deleted without requesting anything
        """
        remover = ConanRemover(self.file_manager, self._user_io, self.remote_manager, remote)
        remover.remove(pattern, src, build_ids, package_ids_filter, force=force)

    def user(self, remote=None, name=None, password=None):
        user = self._localdb.get_username()
        if not name:
            anon = '(anonymous)' if not user else ''
            self._user_io.out.info('Current user: %s %s' % (user, anon))
        else:
            name = None if name == 'none' else name
            anon = '(anonymous)' if not name else ''
            if password is not None:
                token = self.remote_manager.authenticate(remote=remote,
                                                         name=name,
                                                         password=password)
            else:
                token = None
            if name == user:
                self._user_io.out.info('Current user already: %s %s' % (user, anon))
            else:
                self._user_io.out.info('Change user from %s to %s %s' % (user, name, anon))
            self._localdb.set_login((name, token))
