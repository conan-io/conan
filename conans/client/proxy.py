from conans.client.output import ScopedOutput
from conans.util.files import path_exists, rmdir
from conans.model.ref import PackageReference
from conans.errors import ConanException


class ConanfileRemoteProxy(object):
    """ A Remote proxy just for loading conanfiles. It is needed by the DepsBuilder,
    when it has to build the transitive graph of dependencies
    """
    def __init__(self, paths, user_io, conan_loader, remote_manager, remote):
        self._paths = paths
        self._loader = conan_loader
        self._out = user_io.out
        self._remote_manager = remote_manager
        self._remote = remote

    def retrieve_conanfile(self, conan_reference, consumer=False):
        """ returns the requested conanfile object, retrieving it from
        remotes if necessary. Can raise NotFoundException
        """
        output = ScopedOutput(str(conan_reference), self._out)
        conanfile_path = self._paths.conanfile(conan_reference)

        if not self._paths.valid_conan_digest(conan_reference):
            conan_dir_path = self._paths.export(conan_reference)
            if path_exists(conan_dir_path, self._paths.store):
                # If not valid conanfile, ensure empty folder
                output.warn("Bad conanfile detected! Removing export directory... ")
                rmdir(conan_dir_path)
            output.info("Conanfile not found, retrieving from server")
            # If not in localhost, download it. Will raise if not found
            self._remote_manager.get_conanfile(conan_reference, self._remote)
        conanfile = self._loader.load_conan(conanfile_path, output, consumer)
        return conanfile


class ConanRemoteProxy(object):
    """ The remote proxy for binaries, downloads and uploads
    """
    def __init__(self, paths, user_io, remote_manager, remote):
        self._paths = paths
        self._out = user_io.out
        self._remote_manager = remote_manager
        self._remote = remote

    @property
    def remote(self):
        return self._remote

    def upload_conan(self, conan_reference):
        return self._remote_manager.upload_conan(conan_reference, self._remote)

    def upload_package(self, package_reference):
        return self._remote_manager.upload_package(package_reference, self._remote)

    def get_conan_digest(self, conan_ref):
        return self._remote_manager.get_conan_digest(conan_ref, self._remote)

    def search(self, pattern=None, ignorecase=True):
        return self._remote_manager.search(pattern, self._remote, ignorecase)

    def remove(self, conan_ref):
        return self._remote_manager.remove(conan_ref, self._remote)

    def remove_packages(self, conan_ref, remove_ids):
        return self._remote_manager.remove_packages(conan_ref, remove_ids, self._remote)

    def download_packages(self, reference, package_ids):
        assert(isinstance(package_ids, list))
        self._remote_manager.get_conanfile(reference, self._remote)
        output = ScopedOutput(str(reference), self._out)
        for package_id in package_ids:
            package_reference = PackageReference(reference, package_id)
            self.retrieve_remote_package(package_reference, output)

    def retrieve_remote_package(self, package_reference, output):
        package_id = str(package_reference.package_id)
        try:
            output.info("Looking for package %s in remotes" % package_id)
            # Will raise if not found NotFoundException
            self._remote_manager.get_package(package_reference, self._remote)
            output.success('Package installed %s' % package_id)
            return True
        except ConanException as e:
            output.warn('Binary for %s not in remote: %s' % (package_id, str(e)))
            return False
