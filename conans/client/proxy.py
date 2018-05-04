import os

from requests.exceptions import RequestException

from conans.client.loader_parse import load_conanfile_class
from conans.client.output import ScopedOutput
from conans.client.remover import DiskRemover
from conans.client.recorder.action_recorder import INSTALL_ERROR_MISSING, INSTALL_ERROR_NETWORK
from conans.errors import (ConanException, NotFoundException, NoRemoteAvailable)
from conans.model.ref import PackageReference
from conans.util.log import logger
from conans.util.tracer import log_recipe_got_from_local_cache
from conans.client.source import complete_recipe_sources


class ConanProxy(object):
    """ Class to access the conan storage, to perform typical tasks as to get packages,
    getting conanfiles, uploading, removing from remote, etc.
    It uses the registry to control where the packages come from.
    """
    def __init__(self, client_cache, user_io, remote_manager, remote_name, recorder, registry,
                 manifest_manager=False):
        # collaborators
        self._client_cache = client_cache
        self._out = user_io.out
        self._remote_manager = remote_manager
        self._registry = registry
        self._manifest_manager = manifest_manager
        self._recorder = recorder
        # inputs
        self._remote_name = remote_name

    @property
    def registry(self):
        return self._registry

    def package_available(self, package_ref, package_folder, check_outdated):
        """
        Returns True if there is a local or remote package available (and up to date if check_outdated).
        It wont download the package, just check its hash
        """

        output = ScopedOutput(str(package_ref.conan), self._out)
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

    def handle_package_manifest(self, package_ref):
        if self._manifest_manager:
            remote = self._registry.get_ref(package_ref.conan)
            self._manifest_manager.check_package(package_ref, remote)

    def get_recipe(self, conan_reference, check_updates, update):
        with self._client_cache.conanfile_write_lock(conan_reference):
            result = self._get_recipe(conan_reference, check_updates, update)
        return result

    def _get_recipe(self, conan_reference, check_updates, update):
        output = ScopedOutput(str(conan_reference), self._out)
        check_updates = check_updates or update
        # check if it is in disk
        conanfile_path = self._client_cache.conanfile(conan_reference)

        if os.path.exists(conanfile_path):
            if check_updates:
                ret = self.update_available(conan_reference)
                if ret != 0:  # Found and not equal
                    remote, ref_remote = self._get_remote(conan_reference)
                    if ret == 1:
                        if not update:
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
                            DiskRemover(self._client_cache).remove(conan_reference)
                            output.info("Retrieving from remote '%s'..." % remote.name)
                            self._remote_manager.get_recipe(conan_reference, remote)

                            output.info("Updated!")
                    elif ret == -1:
                        if not update:
                            output.info("Current conanfile is newer than %s's one" % remote.name)
                        else:
                            output.error("Current conanfile is newer than %s's one. "
                                         "Run 'conan remove %s' and run install again "
                                         "to replace it." % (remote.name, conan_reference))

            log_recipe_got_from_local_cache(conan_reference)
            self._recorder.recipe_fetched_from_cache(conan_reference)

        else:
            self._retrieve_recipe(conan_reference, output)

        if self._manifest_manager:
            # Just make sure that the recipe sources are there to check
            conanfile = load_conanfile_class(conanfile_path)
            complete_recipe_sources(self._remote_manager, self._client_cache, self._registry,
                                    conanfile, conan_reference)

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
            try:  # get_conan_manifest can fail, not in server
                upstream_manifest = self.get_conan_manifest(conan_reference)
                if upstream_manifest != read_manifest:
                    return 1 if upstream_manifest.time > read_manifest.time else -1
            except (NotFoundException, NoRemoteAvailable):  # 404
                pass

        return 0

    def _retrieve_recipe(self, conan_reference, output):
        """ returns the requested conanfile object, retrieving it from
        remotes if necessary. Can raise NotFoundException
        """
        def _retrieve_from_remote(the_remote):
            output.info("Trying with '%s'..." % the_remote.name)
            self._remote_manager.get_recipe(conan_reference, the_remote)
            self._registry.set_ref(conan_reference, the_remote)
            self._recorder.recipe_downloaded(conan_reference, the_remote.url)

        if self._remote_name:
            output.info("Not found, retrieving from server '%s' " % self._remote_name)
            ref_remote = self._registry.remote(self._remote_name)
        else:
            ref_remote = self._registry.get_ref(conan_reference)
            if ref_remote:
                output.info("Retrieving from predefined remote '%s'" % ref_remote.name)

        if ref_remote:
            try:
                _retrieve_from_remote(ref_remote)
                return
            except NotFoundException:
                msg = "%s was not found in remote '%s'" % (str(conan_reference), ref_remote.name)
                self._recorder.recipe_install_error(conan_reference, INSTALL_ERROR_MISSING,
                                                    msg, ref_remote.url)
                raise NotFoundException(msg)
            except RequestException as exc:
                self._recorder.recipe_install_error(conan_reference, INSTALL_ERROR_NETWORK,
                                                    str(exc), ref_remote.url)
                raise exc

        output.info("Not found in local cache, looking in remotes...")
        remotes = self._registry.remotes
        for remote in remotes:
            logger.debug("Trying with remote %s" % remote.name)
            try:
                _retrieve_from_remote(remote)
                return
            # If not found continue with the next, else raise
            except NotFoundException as exc:
                if remote == remotes[-1]:  # Last element not found
                    msg = "Unable to find '%s' in remotes" % str(conan_reference)
                    logger.debug("Not found in any remote, raising...%s" % exc)
                    self._recorder.recipe_install_error(conan_reference, INSTALL_ERROR_MISSING,
                                                        msg, None)
                    raise NotFoundException(msg)

        raise ConanException("No remote defined")

    def _get_remote(self, conan_ref=None):
        # Prioritize -r , then reference registry and then the default remote
        ref_remote = self._registry.get_ref(conan_ref) if conan_ref else None
        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
        else:
            remote = ref_remote or self._registry.default_remote
        return remote, ref_remote

    def get_conan_manifest(self, conan_ref):
        """ used by update to check the date of packages, require force if older
        """
        remote, current_remote = self._get_remote(conan_ref)
        result = self._remote_manager.get_conan_manifest(conan_ref, remote)
        if not current_remote:
            self._registry.set_ref(conan_ref, remote)
        return result

    def get_package_manifest(self, package_ref):
        """ used by update to check the date of packages, require force if older
        """
        remote, ref_remote = self._get_remote(package_ref.conan)
        result = self._remote_manager.get_package_manifest(package_ref, remote)
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

    def download_packages(self, reference, package_ids):
        assert(isinstance(package_ids, list))
        remote, _ = self._get_remote(reference)
        conanfile_path = self._client_cache.conanfile(reference)
        if not os.path.exists(conanfile_path):
            raise Exception("Download recipe first")
        conanfile = load_conanfile_class(conanfile_path)
        short_paths = conanfile.short_paths
        self._registry.set_ref(reference, remote)
        output = ScopedOutput(str(reference), self._out)
        for package_id in package_ids:
            package_ref = PackageReference(reference, package_id)
            package_folder = self._client_cache.package(package_ref, short_paths=short_paths)
            self._out.info("Downloading %s" % str(package_ref))
            self._remote_manager.get_package(conanfile, package_ref, package_folder, remote, output)
