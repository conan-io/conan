from conans.client.output import ScopedOutput
from conans.util.files import path_exists, rmdir
from conans.model.ref import PackageReference
from conans.errors import (ConanException, ConanConnectionError, ConanOutdatedClient,
                           NotFoundException)
from conans.client.remote_registry import RemoteRegistry
from conans.util.log import logger
import os


class ConanProxy(object):
    """ Class to access the conan storage, to perform typical tasks as to get packages,
    getting conanfiles, uploading, removing from remote, etc.
    It uses the RemoteRegistry to control where the packages come from.
    """
    def __init__(self, paths, user_io, remote_manager, remote_name):
        self._paths = paths
        self._out = user_io.out
        self._remote_manager = remote_manager
        self._registry = RemoteRegistry(self._paths.registry, self._out)
        self._remote_name = remote_name

    @property
    def _defined_remote(self):
        if self._remote_name:
            return self._registry.remote(self._remote_name)
        return self._registry.default_remote

    def get_package(self, package_reference, force_build):
        output = ScopedOutput(str(package_reference.conan), self._out)
        package_folder = self._paths.package(package_reference)
        # Check if package is corrupted
        valid_package_digest = self._paths.valid_package_digest(package_reference)
        if os.path.exists(package_folder) and not valid_package_digest:
            # If not valid package, ensure empty folder
            output.warn("Bad package '%s' detected! Removing "
                        "package directory... " % str(package_reference.package_id))
            rmdir(package_folder)

        if not force_build:
            local_package = os.path.exists(package_folder)
            if local_package:
                output.info('Package installed in %s' % package_folder)
                return True

            output.info('Package not installed')
            remote_package = self.retrieve_remote_package(package_reference, output)
            if remote_package:
                return True
        return False

    def get_conanfile(self, conan_reference):
        output = ScopedOutput(str(conan_reference), self._out)

        # check if it is in disk
        conanfile_path = self._paths.conanfile(conan_reference)
        if path_exists(conanfile_path, self._paths.store):
            # Check manifest integrity
            if not self._paths.valid_conan_digest(conan_reference):
                conan_dir_path = self._paths.export(conan_reference)
                # If not valid conanfile, ensure empty folder
                output.warn("Bad conanfile detected! Removing export directory... ")
                rmdir(conan_dir_path)
                rmdir(self._paths.source(conan_reference))
                self._registry.remove_ref(conan_reference)
                output.info("Retrieving a fresh conanfile from remotes")
                self._retrieve_conanfile(conan_reference, output)
            else:  # Check for updates
                pass  # TODO: Check upstream updates
        else:
            output.info("Conanfile not found, retrieving from server")
            self._retrieve_conanfile(conan_reference, output)
        return conanfile_path


    def _retrieve_conanfile(self, conan_reference, output):
        """ returns the requested conanfile object, retrieving it from
        remotes if necessary. Can raise NotFoundException
        """
        def _retrieve_from_remote(remote):
            result = self._remote_manager.get_conanfile(conan_reference, remote)
            self._registry.set_ref(conan_reference, remote)
            output.success("Found in remote '%s'" % remote.name)
            return result

        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
            return _retrieve_from_remote(remote)

        remotes = self._registry.remotes
        for remote in remotes:
            logger.debug("Trying with remote %s" % remote.name)
            try:
                return _retrieve_from_remote(remote)
            # If exception continue with the next
            except (ConanOutdatedClient, ConanConnectionError) as exc:
                output.warn(str(exc))
                if remote == self._remotes[-1]:  # Last element not found
                    raise ConanConnectionError("All remotes failed")
            except NotFoundException as exc:
                if remote == self._remotes[-1]:  # Last element not found
                    logger.debug("Not found in any remote, raising...%s" % exc)
                    raise

        raise ConanException("No remote defined")

    def upload_conan(self, conan_reference):  
        current_remote = self._registry.get_ref(conan_reference) 
        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
        else:
            if current_remote:
                remote = current_remote
            else:
                remote = self._registry.default_remote
                
        result = self._remote_manager.upload_conan(conan_reference, remote)
        if not current_remote:
            self._registry.set_ref(conan_reference, remote)
        return result

    def upload_package(self, package_reference):
        remote = self._defined_remote
        return self._remote_manager.upload_package(package_reference, remote)

    def get_conan_digest(self, conan_ref):
        """ used by update to check the date of packages, require force if older
        """
        remote = self._defined_remote
        return self._remote_manager.get_conan_digest(conan_ref, remote)

    def search(self, pattern=None, ignorecase=True):
        remote = self._defined_remote
        return self._remote_manager.search(remote, pattern, ignorecase)

    def remove(self, conan_ref):
        remote = self._defined_remote
        result = self._remote_manager.remove(conan_ref, remote)
        self._registry.remove_ref(conan_ref)
        return result

    def remove_packages(self, conan_ref, remove_ids):
        remote = self._defined_remote
        return self._remote_manager.remove_packages(conan_ref, remove_ids, remote)

    def download_packages(self, reference, package_ids):
        assert(isinstance(package_ids, list))
        remote = self._defined_remote
        self._remote_manager.get_conanfile(reference, remote)
        self._registry.set_ref(reference, remote)
        output = ScopedOutput(str(reference), self._out)
        for package_id in package_ids:
            package_reference = PackageReference(reference, package_id)
            self.retrieve_remote_package(package_reference, output)

    def retrieve_remote_package(self, package_reference, output):
        remote = self._registry.get_ref(package_reference.conan)
        if not remote:
            output.warn("Package doesn't have a remote defined")
            return
        package_id = str(package_reference.package_id)
        try:
            output.info("Looking for package %s in remotes" % package_id)
            # Will raise if not found NotFoundException
            self._remote_manager.get_package(package_reference, remote)
            output.success('Package installed %s' % package_id)
            return True
        except ConanException as e:
            output.warn('Binary for %s not in remote: %s' % (package_id, str(e)))
            return False

    def authenticate(self, name, password):
        remote = self._defined_remote
        return self._remote_manager.authenticate(remote, name, password)
