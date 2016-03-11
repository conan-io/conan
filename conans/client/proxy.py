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
    def __init__(self, paths, user_io, remote_manager, remote_name,
                 update=False, check_updates=True):
        self._paths = paths
        self._out = user_io.out
        self._remote_manager = remote_manager
        self._registry = RemoteRegistry(self._paths.registry, self._out)
        self._remote_name = remote_name
        self._update = update
        self._check_updates = check_updates

    def get_package(self, package_reference, force_build):
        """ obtain a package, either from disk or retrieve from remotes if necessary
        and not necessary to build
        """
        output = ScopedOutput(str(package_reference.conan), self._out)
        package_folder = self._paths.package(package_reference)
        # Check if package is corrupted
        read_manifest, expected_manifest = self._paths.package_manifests(package_reference)
        if read_manifest is not None:  # Package exists
            if read_manifest.file_sums != expected_manifest.file_sums:
                # If not valid package, ensure empty folder
                output.warn("Bad package '%s' detected! Removing "
                            "package directory... " % str(package_reference.package_id))
                rmdir(package_folder)
            else:
                try:  # get_conan_digest can fail, not in server
                    upstream_manifest = self.get_package_digest(package_reference)
                    if upstream_manifest.file_sums != read_manifest.file_sums:
                        if upstream_manifest.time > read_manifest.time:
                            output.warn("Current package is older than remote upstream one")
                            if self._update:
                                output.warn("Removing it to retrieve or build an updated one")
                                rmdir(package_folder)
                        else:
                            output.warn("Current package is newer than remote upstream one")
                except ConanException:
                    pass

        if not force_build:
            local_package = os.path.exists(package_folder)
            if local_package:
                output = ScopedOutput(str(package_reference.conan), self._out)
                output.info('Already installed!')
                return True
            return self._retrieve_remote_package(package_reference, output)

        return False

    def get_conanfile(self, conan_reference):
        output = ScopedOutput(str(conan_reference), self._out)

        def _refresh():
            conan_dir_path = self._paths.export(conan_reference)
            rmdir(conan_dir_path)
            rmdir(self._paths.source(conan_reference))
            current_remote, _ = self._get_remote(conan_reference)
            output.info("Retrieving from remote '%s'..." % current_remote.name)
            self._remote_manager.get_conanfile(conan_reference, current_remote)
            if self._update:
                output.info("Updated!")
            else:
                output.info("Installed!")

        # check if it is in disk
        conanfile_path = self._paths.conanfile(conan_reference)
        if path_exists(conanfile_path, self._paths.store):
            # Check manifest integrity
            read_manifest, expected_manifest = self._paths.conan_manifests(conan_reference)
            if read_manifest.file_sums != expected_manifest.file_sums:
                output.warn("Bad conanfile detected! Removing export directory... ")
                _refresh()
            else:  # Check for updates
                if self._check_updates:
                    ret = self.update_available(conan_reference)
                    if ret != 0:  # Found and not equal
                        remote, ref_remote = self._get_remote(conan_reference)
                        if ret == 1:
                            if not self._update:
                                if remote != ref_remote:  # Forced new remote
                                    output.warn("There is a new conanfile in '%s' remote. "
                                                "Execute 'install -u -r %s' to update it."
                                                % (remote.name, remote.name))
                                else:
                                    output.warn("There is a new conanfile in '%s' remote. "
                                                "Execute 'install -u' to update it."
                                                % remote.name)
                                output.warn("Refused to install!")
                            else:
                                if remote != ref_remote:
                                    # Delete packages, could be non coherent with new remote
                                    rmdir(self._paths.packages(conan_reference))
                                _refresh()
                        elif ret == -1:
                            output.error("Current conanfile is newer than %s's one. Remove the local conanfile "\
                                         "and execute install again." % remote.name)
        else:
            self._retrieve_conanfile(conan_reference, output)
        return conanfile_path

    def update_available(self, conan_reference):
        """Returns 0 if the conanfiles are equal, 1 if there is an update and -1 if 
        the local is newer than the remote"""
        if not conan_reference:
            return 0
        read_manifest, _ = self._paths.conan_manifests(conan_reference)
        try:  # get_conan_digest can fail, not in server
            upstream_manifest = self.get_conan_digest(conan_reference)
            if upstream_manifest.file_sums != read_manifest.file_sums:
                return 1 if upstream_manifest.time > read_manifest.time else -1
        except ConanException:
            pass

        return 0

    def _retrieve_conanfile(self, conan_reference, output):
        """ returns the requested conanfile object, retrieving it from
        remotes if necessary. Can raise NotFoundException
        """
        def _retrieve_from_remote(remote):
            output.info("Trying with '%s'..." % remote.name)
            result = self._remote_manager.get_conanfile(conan_reference, remote)
            self._registry.set_ref(conan_reference, remote)
            return result

        if self._remote_name:
            output.info("Not found, retrieving from server '%s' " % self._remote_name)
            remote = self._registry.remote(self._remote_name)
            return _retrieve_from_remote(remote)
        else:
            output.info("Not found, looking in remotes...")

        remotes = self._registry.remotes
        for remote in remotes:
            logger.debug("Trying with remote %s" % remote.name)
            try:
                return _retrieve_from_remote(remote)
            # If exception continue with the next
            except (ConanOutdatedClient, ConanConnectionError) as exc:
                output.warn(str(exc))
                if remote == remotes[-1]:  # Last element not found
                    raise ConanConnectionError("All remotes failed")
            except NotFoundException as exc:
                if remote == remotes[-1]:  # Last element not found
                    logger.debug("Not found in any remote, raising...%s" % exc)
                    raise NotFoundException("Unable to find '%s' in remotes"
                                            % str(conan_reference))

        raise ConanException("No remote defined")

    def upload_conan(self, conan_reference):
        """ upload to defined remote in (-r=remote), to current remote
        or to default remote, in that order.
        If the remote is not set, set it
        """
        remote, ref_remote = self._get_remote(conan_reference)

        result = self._remote_manager.upload_conan(conan_reference, remote)
        if not ref_remote:
            self._registry.set_ref(conan_reference, remote)
        return result

    def _get_remote(self, conan_ref=None):
        # Prioritize -r , then reference registry and then the default remote
        ref_remote = self._registry.get_ref(conan_ref) if conan_ref else None
        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
        else:
            if ref_remote:
                remote = ref_remote
            else:
                remote = self._registry.default_remote
        return remote, ref_remote

    def upload_package(self, package_reference):
        remote, current_remote = self._get_remote(package_reference.conan)

        if not current_remote:
            self._out.warn("Remote for '%s' not defined, uploading to %s"
                           % (str(package_reference.conan), remote.name))
        result = self._remote_manager.upload_package(package_reference, remote)
        if not current_remote:
            self._registry.set_ref(package_reference.conan, remote)
        return result

    def get_conan_digest(self, conan_ref):
        """ used by update to check the date of packages, require force if older
        """
        remote, current_remote = self._get_remote(conan_ref)
        result = self._remote_manager.get_conan_digest(conan_ref, remote)
        if not current_remote:
            self._registry.set_ref(conan_ref, remote)
        return result

    def get_package_digest(self, package_reference):
        """ used by update to check the date of packages, require force if older
        """
        remote, ref_remote = self._get_remote(package_reference.conan)
        result = self._remote_manager.get_package_digest(package_reference, remote)
        if not ref_remote:
            self._registry.set_ref(package_reference.conan, remote)
        return result

    def search(self, pattern=None, ignorecase=True):
        remote, _ = self._get_remote()
        return self._remote_manager.search(remote, pattern, ignorecase)

    def remove(self, conan_ref):
        if not self._remote_name:
            raise ConanException("Cannot remove, remote not defined")
        remote = self._registry.remote(self._remote_name)    
        result = self._remote_manager.remove(conan_ref, remote)
        self._registry.remove_ref(conan_ref)
        return result

    def remove_packages(self, conan_ref, remove_ids):
        if not self._remote_name:
            raise ConanException("Cannot remove, remote not defined")
        remote = self._registry.remote(self._remote_name)
        return self._remote_manager.remove_packages(conan_ref, remove_ids, remote)

    def download_packages(self, reference, package_ids):
        assert(isinstance(package_ids, list))
        remote, _ = self._get_remote(reference)
        self._remote_manager.get_conanfile(reference, remote)
        self._registry.set_ref(reference, remote)
        output = ScopedOutput(str(reference), self._out)
        for package_id in package_ids:
            package_reference = PackageReference(reference, package_id)
            self._retrieve_remote_package(package_reference, output, remote)

    def _retrieve_remote_package(self, package_reference, output, remote=None):

        if remote is None:
            remote = self._registry.get_ref(package_reference.conan)
        if not remote:
            output.error("Package doesn't have a remote defined")
            return False
        package_id = str(package_reference.package_id)
        try:
            output.info("Looking for package %s in remote '%s' " % (package_id, remote.name))
            # Will raise if not found NotFoundException
            self._remote_manager.get_package(package_reference, remote)
            output.success('Package installed %s' % package_id)
            return True
        except ConanException as e:
            output.warn('Binary for %s not in remote: %s' % (package_id, str(e)))
            return False

    def authenticate(self, name, password):
        remote, _ = self._get_remote()
        return self._remote_manager.authenticate(remote, name, password)
