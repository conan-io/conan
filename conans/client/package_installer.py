import os

from conans.errors import NotFoundException, NoRemoteAvailable
from conans.util.files import rmdir
from conans.util.tracer import log_package_got_from_local_cache
from conans.model.manifest import FileTreeManifest


def get_package(conanfile, package_ref, package_folder, output, recorder, proxy, update):
    # TODO: This access to proxy attributes has to be improved
    remote_manager = proxy._remote_manager
    registry = proxy.registry
    if update:
        _remove_if_outdated(package_folder, package_ref, proxy, output)
    local_package = os.path.exists(package_folder)
    if local_package:
        output.success('Already installed!')
        log_package_got_from_local_cache(package_ref)
        recorder.package_fetched_from_cache(package_ref)
        return False
    else:
        remote = registry.get_ref(package_ref.conan)
        # remote will be defined, as package availability has been checked from installer
        try:
            remote_manager.get_package(package_ref, package_folder, remote, output, recorder)
        except NotFoundException:
            from conans.client.installer import raise_package_not_found_error
            raise_package_not_found_error(conanfile, package_ref.conan, package_ref.package_id,
                                          output, recorder, remote.url)
        return True


def _remove_if_outdated(package_folder, package_ref, proxy, output):
    if os.path.exists(package_folder):
        try:  # get_conan_digest can fail, not in server
            # FIXME: This can iterate remotes to get and associate in registry
            upstream_manifest = proxy.get_package_manifest(package_ref)
        except NotFoundException:
            output.warn("Can't update, no package in remote")
        except NoRemoteAvailable:
            output.warn("Can't update, no remote defined")
        else:
            read_manifest = FileTreeManifest.load(package_folder)
            if upstream_manifest != read_manifest:
                if upstream_manifest.time > read_manifest.time:
                    output.warn("Current package is older than remote upstream one")
                    output.warn("Removing it to retrieve or build an updated one")
                    rmdir(package_folder)
                else:
                    output.warn("Current package is newer than remote upstream one")
