import os
import shutil
import time
import traceback

from requests.exceptions import ConnectionError

from conans import DEFAULT_REVISION_V1
from conans.client.cache.remote_registry import Remote
from conans.errors import ConanConnectionError, ConanException, NotFoundException, \
    NoRestV2Available, PackageNotFoundException
from conans.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, rm_conandir
from conans.search.search import filter_packages
from conans.util import progress_bar
from conans.util.env_reader import get_env
from conans.util.files import make_read_only, mkdir, tar_extract, touch_folder, md5sum, sha1sum
from conans.util.log import logger
# FIXME: Eventually, when all output is done, tracer functions should be moved to the recorder class
from conans.util.tracer import (log_package_download,
                                log_recipe_download, log_recipe_sources_download,
                                log_uncompressed_file)


class RemoteManager(object):
    """ Will handle the remotes to get recipes, packages etc """

    def __init__(self, cache, auth_manager, output, hook_manager):
        self._cache = cache
        self._output = output
        self._auth_manager = auth_manager
        self._hook_manager = hook_manager

    def check_credentials(self, remote):
        self._call_remote(remote, "check_credentials")

    def get_recipe_snapshot(self, ref, remote):
        assert ref.revision, "get_recipe_snapshot requires revision"
        return self._call_remote(remote, "get_recipe_snapshot", ref)

    def get_package_snapshot(self, pref, remote):
        assert pref.ref.revision, "upload_package requires RREV"
        assert pref.revision, "get_package_snapshot requires PREV"
        return self._call_remote(remote, "get_package_snapshot", pref)

    def upload_recipe(self, ref, files_to_upload, deleted, remote, retry, retry_wait):
        assert ref.revision, "upload_recipe requires RREV"
        self._call_remote(remote, "upload_recipe", ref, files_to_upload, deleted,
                          retry, retry_wait)

    def upload_package(self, pref, files_to_upload, deleted, remote, retry, retry_wait):
        assert pref.ref.revision, "upload_package requires RREV"
        assert pref.revision, "upload_package requires PREV"
        self._call_remote(remote, "upload_package", pref,
                          files_to_upload, deleted, retry, retry_wait)

    def get_recipe_manifest(self, ref, remote):
        ref = self._resolve_latest_ref(ref, remote)
        return self._call_remote(remote, "get_recipe_manifest", ref), ref

    def get_package_manifest(self, pref, remote):
        pref = self._resolve_latest_pref(pref, remote)
        return self._call_remote(remote, "get_package_manifest", pref), pref

    def get_package_info(self, pref, remote):
        """ Read a package ConanInfo from remote
        """
        pref = self._resolve_latest_pref(pref, remote)
        return self._call_remote(remote, "get_package_info", pref), pref

    def get_recipe(self, ref, remote):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""

        self._hook_manager.execute("pre_download_recipe", reference=ref, remote=remote)
        package_layout = self._cache.package_layout(ref)
        package_layout.export_remove()

        ref = self._resolve_latest_ref(ref, remote)

        t1 = time.time()
        download_export = package_layout.download_export()
        zipped_files = self._call_remote(remote, "get_recipe", ref, download_export)
        duration = time.time() - t1
        log_recipe_download(ref, duration, remote.name, zipped_files)

        recipe_checksums = calc_files_checksum(zipped_files)

        export_folder = package_layout.export()
        tgz_file = zipped_files.pop(EXPORT_TGZ_NAME, None)
        check_compressed_files(EXPORT_TGZ_NAME, zipped_files)
        if tgz_file:
            uncompress_file(tgz_file, export_folder, output=self._output)
        mkdir(export_folder)
        for file_name, file_path in zipped_files.items():  # copy CONANFILE
            os.rename(file_path, os.path.join(export_folder, file_name))

        # Make sure that the source dir is deleted
        rm_conandir(package_layout.source())
        touch_folder(export_folder)
        conanfile_path = package_layout.conanfile()

        with package_layout.update_metadata() as metadata:
            metadata.recipe.revision = ref.revision
            metadata.recipe.checksums = recipe_checksums

        self._hook_manager.execute("post_download_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        return ref

    def get_recipe_sources(self, ref, layout, remote):
        assert ref.revision, "get_recipe_sources requires RREV"
        t1 = time.time()

        download_folder = layout.download_export()
        export_sources_folder = layout.export_sources()
        zipped_files = self._call_remote(remote, "get_recipe_sources", ref, download_folder)
        if not zipped_files:
            mkdir(export_sources_folder)  # create the folder even if no source files
            return

        duration = time.time() - t1
        log_recipe_sources_download(ref, duration, remote.name, zipped_files)

        tgz_file = zipped_files[EXPORT_SOURCES_TGZ_NAME]
        check_compressed_files(EXPORT_SOURCES_TGZ_NAME, zipped_files)
        uncompress_file(tgz_file, export_sources_folder, output=self._output)
        touch_folder(export_sources_folder)

    def get_package(self, conanfile, pref, layout, remote, output, recorder):
        conanfile_path = layout.conanfile()
        self._hook_manager.execute("pre_download_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.id, remote=remote,
                                   conanfile=conanfile)

        output.info("Retrieving package %s from remote '%s' " % (pref.id, remote.name))
        layout.package_remove(pref)  # Remove first the destination folder
        with layout.set_dirty_context_manager(pref):
            self._get_package(layout, pref, remote, output, recorder)

        self._hook_manager.execute("post_download_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.id, remote=remote,
                                   conanfile=conanfile)

    def _get_package(self, layout, pref, remote, output, recorder):
        t1 = time.time()
        try:
            pref = self._resolve_latest_pref(pref, remote)
            snapshot = self._call_remote(remote, "get_package_snapshot", pref)
            if not is_package_snapshot_complete(snapshot):
                raise PackageNotFoundException(pref)

            download_pkg_folder = layout.download_package(pref)
            # Download files to the pkg_tgz folder, not to the final one
            zipped_files = self._call_remote(remote, "get_package", pref, download_pkg_folder)

            # Compute and update the package metadata
            package_checksums = calc_files_checksum(zipped_files)
            with layout.update_metadata() as metadata:
                metadata.packages[pref.id].revision = pref.revision
                metadata.packages[pref.id].recipe_revision = pref.ref.revision
                metadata.packages[pref.id].checksums = package_checksums
                metadata.packages[pref.id].remote = remote.name

            duration = time.time() - t1
            log_package_download(pref, duration, remote, zipped_files)

            tgz_file = zipped_files.pop(PACKAGE_TGZ_NAME, None)
            check_compressed_files(PACKAGE_TGZ_NAME, zipped_files)
            package_folder = layout.package(pref)
            if tgz_file:  # This must happen always, but just in case
                # TODO: The output could be changed to the package one, but
                uncompress_file(tgz_file, package_folder, output=self._output)
            mkdir(package_folder)  # Just in case it doesn't exist, because uncompress did nothing
            for file_name, file_path in zipped_files.items():  # copy CONANINFO and CONANMANIFEST
                os.rename(file_path, os.path.join(package_folder, file_name))

            # Issue #214 https://github.com/conan-io/conan/issues/214
            touch_folder(package_folder)
            if get_env("CONAN_READ_ONLY_CACHE", False):
                make_read_only(package_folder)
            recorder.package_downloaded(pref, remote.url)
            output.success('Package installed %s' % pref.id)
            output.info("Downloaded package revision %s" % pref.revision)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        except BaseException as e:
            output.error("Exception while getting package: %s" % str(pref.id))
            output.error("Exception: %s %s" % (type(e), str(e)))
            raise

    def search_recipes(self, remote, pattern=None, ignorecase=True):
        """
        returns (dict str(ref): {packages_info}
        """
        return self._call_remote(remote, "search", pattern, ignorecase)

    def search_packages(self, remote, ref, query):
        packages = self._call_remote(remote, "search_packages", ref, query)
        packages = filter_packages(query, packages)
        return packages

    def remove_recipe(self, ref, remote):
        return self._call_remote(remote, "remove_recipe", ref)

    def remove_packages(self, ref, remove_ids, remote):
        return self._call_remote(remote, "remove_packages", ref, remove_ids)

    def get_recipe_path(self, ref, path, remote):
        return self._call_remote(remote, "get_recipe_path", ref, path)

    def get_package_path(self, pref, path, remote):
        return self._call_remote(remote, "get_package_path", pref, path)

    def authenticate(self, remote, name, password):
        return self._call_remote(remote, 'authenticate', name, password)

    def get_recipe_revisions(self, ref, remote):
        return self._call_remote(remote, "get_recipe_revisions", ref)

    def get_package_revisions(self, pref, remote):
        revisions = self._call_remote(remote, "get_package_revisions", pref)
        return revisions

    def get_latest_recipe_revision(self, ref, remote):
        revision = self._call_remote(remote, "get_latest_recipe_revision", ref)
        return revision

    def get_latest_package_revision(self, pref, remote):
        revision = self._call_remote(remote, "get_latest_package_revision", pref)
        return revision

    def _resolve_latest_ref(self, ref, remote):
        if ref.revision is None:
            try:
                ref = self.get_latest_recipe_revision(ref, remote)
            except NoRestV2Available:
                ref = ref.copy_with_rev(DEFAULT_REVISION_V1)
        return ref

    def _resolve_latest_pref(self, pref, remote):
        if pref.revision is None:
            try:
                pref = self.get_latest_package_revision(pref, remote)
            except NoRestV2Available:
                pref = pref.copy_with_revs(pref.ref.revision, DEFAULT_REVISION_V1)
        return pref

    def _call_remote(self, remote, method, *args, **kwargs):
        assert(isinstance(remote, Remote))
        try:
            return self._auth_manager.call_rest_api_method(remote, method, *args, **kwargs)
        except ConnectionError as exc:
            raise ConanConnectionError(("%s\n\nUnable to connect to %s=%s\n" +
                                        "1. Make sure the remote is reachable or,\n" +
                                        "2. Disable it by using conan remote disable,\n" +
                                        "Then try again."
                                        ) % (str(exc), remote.name, remote.url))
        except ConanException as exc:
            exc.remote = remote
            raise
        except Exception as exc:
            logger.error(traceback.format_exc())
            raise ConanException(exc, remote=remote)


def calc_files_checksum(files):
    return {file_name: {"md5": md5sum(path), "sha1": sha1sum(path)}
            for file_name, path in files.items()}


def is_package_snapshot_complete(snapshot):
    for keyword in ["conaninfo", "conanmanifest", "conan_package"]:
        if not any(keyword in key for key in snapshot):
            return False
    return True


def check_compressed_files(tgz_name, files):
    bare_name = os.path.splitext(tgz_name)[0]
    for f in files:
        if f == tgz_name:
            continue
        if bare_name == os.path.splitext(f)[0]:
            raise ConanException("This Conan version is not prepared to handle '%s' file format. "
                                 "Please upgrade conan client." % f)


def uncompress_file(src_path, dest_folder, output):
    t1 = time.time()
    try:
        with progress_bar.open_binary(src_path, output, "Decompressing %s" % os.path.basename(
                src_path)) as file_handler:
            tar_extract(file_handler, dest_folder)
    except Exception as e:
        error_msg = "Error while downloading/extracting files to %s\n%s\n" % (dest_folder, str(e))
        # try to remove the files
        try:
            if os.path.exists(dest_folder):
                shutil.rmtree(dest_folder)
                error_msg += "Folder removed"
        except Exception:
            error_msg += "Folder not removed, files/package might be damaged, remove manually"
        raise ConanException(error_msg)

    duration = time.time() - t1
    log_uncompressed_file(src_path, duration, dest_folder)
