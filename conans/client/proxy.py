import os

from conans.client.loader_parse import load_conanfile_class
from conans.client.local_file_getter import get_path
from conans.client.output import ScopedOutput
from conans.client.remote_registry import RemoteRegistry
from conans.client.remover import DiskRemover
from conans.errors import (ConanException, NotFoundException, NoRemoteAvailable)
from conans.model.ref import PackageReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME
from conans.util.files import rmdir, mkdir
from conans.util.log import logger
from conans.util.tracer import log_package_got_from_local_cache,\
    log_recipe_got_from_local_cache


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
            except (NotFoundException, NoRemoteAvailable):  # 404 or no remote
                return False

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
                except NotFoundException:
                    pass

        local_package = os.path.exists(package_folder)
        if local_package:
            output.success('Already installed!')
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

    def get_recipe_sources(self, conan_reference, short_paths=False):
        export_path = self._client_cache.export(conan_reference)
        sources_folder = self._client_cache.export_sources(conan_reference, short_paths)
        if os.path.exists(sources_folder):
            return

        current_remote = self._registry.get_ref(conan_reference)
        if not current_remote:
            raise ConanException("Error while trying to get recipe sources for %s. "
                                 "No remote defined" % str(conan_reference))
        else:
            self._remote_manager.get_recipe_sources(conan_reference, export_path, sources_folder,
                                                    current_remote)

    def get_recipe(self, conan_reference):
        with self._client_cache.conanfile_write_lock(conan_reference):
            result = self._get_recipe(conan_reference)
        return result

    def _get_recipe(self, conan_reference):
        output = ScopedOutput(str(conan_reference), self._out)

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
                            export_path = self._client_cache.export(conan_reference)
                            DiskRemover(self._client_cache).remove(conan_reference)
                            output.info("Retrieving from remote '%s'..." % remote.name)
                            self._remote_manager.get_recipe(conan_reference, export_path, remote)
                            output.info("Updated!")
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
            conanfile = load_conanfile_class(conanfile_path)
            self.get_recipe_sources(conan_reference, conanfile.short_paths)
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
            except (NotFoundException, NoRemoteAvailable):  # 404
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
            ref_remote = self._registry.remote(self._remote_name)
        else:
            ref_remote = self._registry.get_ref(conan_reference)
            if ref_remote:
                output.info("Retrieving from predefined remote '%s'" % ref_remote.name)

        if ref_remote:
            try:
                return _retrieve_from_remote(ref_remote)
            except NotFoundException:
                raise NotFoundException("%s was not found in remote '%s'" % (str(conan_reference),
                                                                             ref_remote.name))

        output.info("Not found in local cache, looking in remotes...")
        remotes = self._registry.remotes
        for remote in remotes:
            logger.debug("Trying with remote %s" % remote.name)
            try:
                return _retrieve_from_remote(remote)
            # If not found continue with the next, else raise
            except NotFoundException as exc:
                if remote == remotes[-1]:  # Last element not found
                    logger.debug("Not found in any remote, raising...%s" % exc)
                    raise NotFoundException("Unable to find '%s' in remotes"
                                            % str(conan_reference))

        raise ConanException("No remote defined")

    def complete_recipe_sources(self, conanfile, conan_reference, force_complete=True, short_paths=False):
        sources_folder = self._client_cache.export_sources(conan_reference, short_paths)
        if not hasattr(conanfile, "exports_sources"):
            mkdir(sources_folder)
            return None

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
                self.get_recipe_sources(conan_reference, short_paths=short_paths)
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
        conan_file_path = self._client_cache.conanfile(conan_reference)
        conanfile = load_conanfile_class(conan_file_path)
        ignore_deleted_file = self.complete_recipe_sources(conanfile, conan_reference,
                                                           force_complete=False,
                                                           short_paths=conanfile.short_paths)
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

    def upload_package(self, package_ref, retry, retry_wait, skip_upload, integrity_check):
        remote, current_remote = self._get_remote(package_ref.conan)
        if not current_remote:
            self._out.warn("Remote for '%s' not defined, uploading to %s"
                           % (str(package_ref.conan), remote.name))
        result = self._remote_manager.upload_package(package_ref, remote, retry, retry_wait,
                                                     skip_upload, integrity_check)
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

    def search_remotes(self, pattern=None, ignorecase=True):
        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
            search_result = self._remote_manager.search_recipes(remote, pattern, ignorecase)
            return search_result

        for remote in self._registry.remotes:
            search_result = self._remote_manager.search_recipes(remote, pattern, ignorecase)
            if search_result:
                return search_result

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

    def get_path(self, conan_ref, package_id, path):
        if not self._remote_name:
            return get_path(self._client_cache, conan_ref, package_id, path)
        else:
            remote = self._registry.remote(self._remote_name)
            return self._remote_manager.get_path(conan_ref, package_id, path, remote)

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
            self._out.info("Downloading %s" % str(package_ref))
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
        except NotFoundException as e:
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
