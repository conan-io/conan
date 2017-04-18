from conans.client.output import ScopedOutput
from conans.util.files import rmdir
from conans.model.ref import PackageReference
from conans.errors import (ConanException, ConanConnectionError, ConanOutdatedClient,
                           NotFoundException)
from conans.client.remote_registry import RemoteRegistry
from conans.util.log import logger
import os
from conans.paths import rm_conandir, EXPORT_SOURCES_DIR, EXPORT_SOURCES_TGZ_NAME
from conans.client.remover import DiskRemover
from conans.util.tracer import log_package_got_from_local_cache,\
    log_recipe_got_from_local_cache
from conans.client.loader_parse import load_conanfile_class


class ConanProxy(object):
    """ Class to access the conan storage, to perform typical tasks as to get packages,
    getting conanfiles, uploading, removing from remote, etc.
    It uses the RemoteRegistry to control where the packages come from.
    """
    def __init__(self, client_cache, user_io, remote_manager, remote_name,
                 update=False, check_updates=False, manifest_manager=False):
        self._client_cache = client_cache
        self._out = user_io.out
        self._remote_manager = remote_manager
        self._registry = RemoteRegistry(self._client_cache.registry, self._out)
        self._remote_name = remote_name
        self._update = update
        self._check_updates = check_updates or update  # Update forces check (and of course the update)
        self._manifest_manager = manifest_manager

    @property
    def registry(self):
        return self._registry

    def package_available(self, package_ref, short_paths, check_outdated):
        """
        Returns True if there is a local or remote package available (and up to date if check_outdated).
        It wont download the package, just check its hash
        """

        output = ScopedOutput(str(package_ref.conan), self._out)
        package_folder = self._client_cache.package(package_ref, short_paths=short_paths)

        remote_info = None
        # No package in local cache
        if not os.path.exists(package_folder):
            try:
                remote_info = self.get_package_info(package_ref)
            except ConanException:
                return False  # Not local nor remote

        # Maybe we have the package (locally or in remote) but it's outdated
        if check_outdated:
            if remote_info:
                package_hash = remote_info.recipe_hash
            else:
                package_hash = self._client_cache.read_package_recipe_hash(package_folder)
            local_recipe_hash = self._client_cache.load_manifest(package_ref.conan).summary_hash
            up_to_date = local_recipe_hash == package_hash
            if not up_to_date:
                output.info("Outdated package!")
            else:
                output.info("Package is up to date")
            return up_to_date

        return True

    def get_package(self, package_ref, short_paths):
        """ obtain a package, either from disk or retrieve from remotes if necessary
        and not necessary to build
        """
        output = ScopedOutput(str(package_ref.conan), self._out)
        package_folder = self._client_cache.package(package_ref, short_paths=short_paths)

        # Check current package status
        if os.path.exists(package_folder):
            if self._check_updates:
                read_manifest = self._client_cache.load_package_manifest(package_ref)
                try:  # get_conan_digest can fail, not in server
                    upstream_manifest = self.get_package_digest(package_ref)
                    if upstream_manifest != read_manifest:
                        if upstream_manifest.time > read_manifest.time:
                            output.warn("Current package is older than remote upstream one")
                            if self._update:
                                output.warn("Removing it to retrieve or build an updated one")
                                rmdir(package_folder)
                        else:
                            output.warn("Current package is newer than remote upstream one")
                except ConanException:
                    pass

        installed = False
        local_package = os.path.exists(package_folder)
        if local_package:
            output.info('Already installed!')
            installed = True
            log_package_got_from_local_cache(package_ref)
        else:
            installed = self._retrieve_remote_package(package_ref, package_folder,
                                                      output)
        self.handle_package_manifest(package_ref, installed)
        return installed

    def handle_package_manifest(self, package_ref, installed):
        if installed and self._manifest_manager:
            remote = self._registry.get_ref(package_ref.conan)
            self._manifest_manager.check_package(package_ref, remote)

    def get_recipe_sources(self, conan_reference):
        export_path = self._client_cache.export(conan_reference)
        sources_folder = os.path.join(export_path, EXPORT_SOURCES_DIR)
        if os.path.exists(sources_folder):
            return

        current_remote = self._registry.get_ref(conan_reference)
        if not current_remote:
            raise ConanException("Error while trying to get recipe sources for %s. "
                                 "No remote defined" % str(conan_reference))
        else:
            self._remote_manager.get_recipe_sources(conan_reference, export_path, current_remote)

    def get_recipe(self, conan_reference):
        output = ScopedOutput(str(conan_reference), self._out)

        def _refresh():
            export_path = self._client_cache.export(conan_reference)
            rmdir(export_path)
            # It might need to remove shortpath
            rm_conandir(self._client_cache.source(conan_reference))
            current_remote, _ = self._get_remote(conan_reference)
            output.info("Retrieving from remote '%s'..." % current_remote.name)
            self._remote_manager.get_recipe(conan_reference, export_path, current_remote)
            if self._update:
                output.info("Updated!")
            else:
                output.info("Installed!")

        # check if it is in disk
        conanfile_path = self._client_cache.conanfile(conan_reference)

        if os.path.exists(conanfile_path):
            log_recipe_got_from_local_cache(conan_reference)
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
                                DiskRemover(self._client_cache).remove_packages(conan_reference)
                            _refresh()
                    elif ret == -1:
                        if not self._update:
                            output.info("Current conanfile is newer "
                                        "than %s's one" % remote.name)
                        else:
                            output.error("Current conanfile is newer than %s's one. "
                                         "Run 'conan remove %s' and run install again "
                                         "to replace it." % (remote.name, conan_reference))

        else:
            self._retrieve_recipe(conan_reference, output)

        if self._manifest_manager:
            # Just make sure that the recipe sources are there to check
            self.get_recipe_sources(conan_reference)
            remote = self._registry.get_ref(conan_reference)
            self._manifest_manager.check_recipe(conan_reference, remote)

        return conanfile_path

    def update_available(self, conan_reference):
        """Returns 0 if the conanfiles are equal, 1 if there is an update and -1 if
        the local is newer than the remote"""
        if not conan_reference:
            return 0
        read_manifest, _ = self._client_cache.conan_manifests(conan_reference)
        if read_manifest:
            try:  # get_conan_digest can fail, not in server
                upstream_manifest = self.get_conan_digest(conan_reference)
                if upstream_manifest != read_manifest:
                    return 1 if upstream_manifest.time > read_manifest.time else -1
            except ConanException:
                pass

        return 0

    def _retrieve_recipe(self, conan_reference, output):
        """ returns the requested conanfile object, retrieving it from
        remotes if necessary. Can raise NotFoundException
        """
        def _retrieve_from_remote(remote):
            output.info("Trying with '%s'..." % remote.name)
            export_path = self._client_cache.export(conan_reference)
            result = self._remote_manager.get_recipe(conan_reference, export_path, remote)
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

    def complete_recipe_sources(self, conan_reference, force_complete=True):
        export_path = self._client_cache.export(conan_reference)
        sources_folder = os.path.join(export_path, EXPORT_SOURCES_DIR)
        ignore_deleted_file = None
        if not os.path.exists(sources_folder):
            # If not path to sources exists, we have a problem, at least an empty folder
            # should be there
            upload_remote, current_remote = self._get_remote(conan_reference)
            if not current_remote:
                raise ConanException("Trying to upload a package recipe without sources, "
                                     "and the remote for the sources no longer exists")
            if force_complete or current_remote != upload_remote:
                # If uploading to a different remote than the one from which the recipe
                # was retrieved, we definitely need to get the sources, so the recipe is complete
                self.get_recipe_sources(conan_reference)
            else:
                # But if same remote, no need to upload again the TGZ, it is already in the server
                # But the upload API needs to know it to not remove the server file.
                ignore_deleted_file = EXPORT_SOURCES_TGZ_NAME
        return ignore_deleted_file

    def upload_recipe(self, conan_reference, retry, retry_wait, skip_upload):
        """ upload to defined remote in (-r=remote), to current remote
        or to default remote, in that order.
        If the remote is not set, set it
        """
        ignore_deleted_file = self.complete_recipe_sources(conan_reference, force_complete=False)
        remote, ref_remote = self._get_remote(conan_reference)

        result = self._remote_manager.upload_recipe(conan_reference, remote, retry, retry_wait,
                                                    ignore_deleted_file=ignore_deleted_file,
                                                    skip_upload=skip_upload)
        if not ref_remote and not skip_upload:
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

    def upload_package(self, package_ref, retry, retry_wait, skip_upload):
        remote, current_remote = self._get_remote(package_ref.conan)
        if not current_remote:
            self._out.warn("Remote for '%s' not defined, uploading to %s"
                           % (str(package_ref.conan), remote.name))
        result = self._remote_manager.upload_package(package_ref, remote, retry, retry_wait, skip_upload)
        if not current_remote and not skip_upload:
            self._registry.set_ref(package_ref.conan, remote)
        return result

    def get_conan_digest(self, conan_ref):
        """ used by update to check the date of packages, require force if older
        """
        remote, current_remote = self._get_remote(conan_ref)
        result = self._remote_manager.get_conan_digest(conan_ref, remote)
        if not current_remote:
            self._registry.set_ref(conan_ref, remote)
        return result

    def get_package_digest(self, package_ref):
        """ used by update to check the date of packages, require force if older
        """
        remote, ref_remote = self._get_remote(package_ref.conan)
        result = self._remote_manager.get_package_digest(package_ref, remote)
        if not ref_remote:
            self._registry.set_ref(package_ref.conan, remote)
        return result

    def get_package_info(self, package_ref):
        """ Gets the package info to check if outdated
        """
        remote, ref_remote = self._get_remote(package_ref.conan)
        result = self._remote_manager.get_package_info(package_ref, remote)
        if not ref_remote:
            self._registry.set_ref(package_ref.conan, remote)
        return result

    def search(self, pattern=None, ignorecase=True):
        remote, _ = self._get_remote()
        return self._remote_manager.search(remote, pattern, ignorecase)

    def search_remotes(self, pattern=None, ignorecase=True):
        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
            search_result = self._remote_manager.search(remote, pattern, ignorecase)
            return search_result

        for remote in self._registry.remotes:
            search_result = self._remote_manager.search(remote, pattern, ignorecase)
            if search_result:
                return search_result

    def search_packages(self, reference, query):
        remote, _ = self._get_remote()
        return self._remote_manager.search_packages(remote, reference, query)

    def remove(self, conan_ref):
        if not self._remote_name:
            raise ConanException("Cannot remove, remote not defined")
        remote = self._registry.remote(self._remote_name)
        result = self._remote_manager.remove(conan_ref, remote)
        current_remote = self._registry.get_ref(conan_ref)
        if current_remote == remote:
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
        export_path = self._client_cache.export(reference)
        self._remote_manager.get_recipe(reference, export_path, remote)
        conanfile_path = self._client_cache.conanfile(reference)
        conanfile = load_conanfile_class(conanfile_path)
        short_paths = conanfile.short_paths
        self._registry.set_ref(reference, remote)
        output = ScopedOutput(str(reference), self._out)
        for package_id in package_ids:
            package_ref = PackageReference(reference, package_id)
            package_folder = self._client_cache.package(package_ref, short_paths=short_paths)
            self._retrieve_remote_package(package_ref, package_folder, output, remote)

    def _retrieve_remote_package(self, package_ref, package_folder, output, remote=None):

        if remote is None:
            remote = self._registry.get_ref(package_ref.conan)
        if not remote:
            output.warn("Package doesn't have a remote defined. "
                        "Probably created locally and not uploaded")
            return False
        package_id = str(package_ref.package_id)
        try:
            output.info("Looking for package %s in remote '%s' " % (package_id, remote.name))
            # Will raise if not found NotFoundException
            self._remote_manager.get_package(package_ref, package_folder, remote)
            output.success('Package installed %s' % package_id)
            return True
        except ConanConnectionError:
            raise  # This shouldn't be skipped
        except ConanException as e:
            output.warn('Binary for %s not in remote: %s' % (package_id, str(e)))
            return False

    def authenticate(self, name, password):
        if not name:  # List all users, from all remotes
            remotes = self._registry.remotes
            if not remotes:
                self._out.error("No remotes defined")
            for remote in remotes:
                self._remote_manager.authenticate(remote, None, None)
            return
        remote, _ = self._get_remote()
        return self._remote_manager.authenticate(remote, name, password)
