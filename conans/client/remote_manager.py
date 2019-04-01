import os
import traceback

import shutil
import time
from requests.exceptions import ConnectionError

from conans import DEFAULT_REVISION_V1
from conans.client.cache.remote_registry import Remote
from conans.client.source import merge_directories
from conans.errors import ConanConnectionError, ConanException, NotFoundException, \
    NoRestV2Available, PackageNotFoundException
from conans.paths import EXPORT_SOURCES_DIR_OLD, \
    EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, rm_conandir
from conans.search.search import filter_packages
from conans.util import progress_bar
from conans.util.env_reader import get_env
from conans.util.files import make_read_only, mkdir, rmdir, tar_extract, touch_folder
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
        dest_folder = self._cache.export(ref)
        rmdir(dest_folder)

        ref = self._resolve_latest_ref(ref, remote)

        t1 = time.time()
        zipped_files = self._call_remote(remote, "get_recipe", ref, dest_folder)
        duration = time.time() - t1
        log_recipe_download(ref, duration, remote.name, zipped_files)

        unzip_and_get_files(zipped_files, dest_folder, EXPORT_TGZ_NAME, output=self._output)
        # Make sure that the source dir is deleted
        rm_conandir(self._cache.source(ref))
        touch_folder(dest_folder)
        conanfile_path = self._cache.conanfile(ref)

        with self._cache.package_layout(ref).update_metadata() as metadata:
            metadata.recipe.revision = ref.revision

        self._hook_manager.execute("post_download_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        return ref

    def get_recipe_sources(self, ref, export_folder, export_sources_folder, remote):
        assert ref.revision, "get_recipe_sources requires RREV"
        t1 = time.time()

        zipped_files = self._call_remote(remote, "get_recipe_sources", ref, export_folder)
        if not zipped_files:
            mkdir(export_sources_folder)  # create the folder even if no source files
            return

        duration = time.time() - t1
        log_recipe_sources_download(ref, duration, remote.name, zipped_files)

        unzip_and_get_files(zipped_files, export_sources_folder, EXPORT_SOURCES_TGZ_NAME,
                            output=self._output)
        # REMOVE in Conan 2.0
        c_src_path = os.path.join(export_sources_folder, EXPORT_SOURCES_DIR_OLD)
        if os.path.exists(c_src_path):
            merge_directories(c_src_path, export_sources_folder)
            rmdir(c_src_path)
        touch_folder(export_sources_folder)

    def get_package(self, pref, dest_folder, remote, output, recorder):

        conanfile_path = self._cache.conanfile(pref.ref)
        self._hook_manager.execute("pre_download_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.id, remote=remote)
        output.info("Retrieving package %s from remote '%s' " % (pref.id, remote.name))
        rm_conandir(dest_folder)  # Remove first the destination folder
        t1 = time.time()
        try:
            pref = self._resolve_latest_pref(pref, remote)
            snapshot = self._call_remote(remote, "get_package_snapshot", pref)
            if not is_package_snapshot_complete(snapshot):
                raise PackageNotFoundException(pref)
            zipped_files = self._call_remote(remote, "get_package", pref, dest_folder)

            with self._cache.package_layout(pref.ref).update_metadata() as metadata:
                metadata.packages[pref.id].revision = pref.revision
                metadata.packages[pref.id].recipe_revision = pref.ref.revision

            duration = time.time() - t1
            log_package_download(pref, duration, remote, zipped_files)
            unzip_and_get_files(zipped_files, dest_folder, PACKAGE_TGZ_NAME, output=self._output)
            # Issue #214 https://github.com/conan-io/conan/issues/214
            touch_folder(dest_folder)
            if get_env("CONAN_READ_ONLY_CACHE", False):
                make_read_only(dest_folder)
            recorder.package_downloaded(pref, remote.url)
            output.success('Package installed %s' % pref.id)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        except BaseException as e:
            output.error("Exception while getting package: %s" % str(pref.id))
            output.error("Exception: %s %s" % (type(e), str(e)))
            try:
                output.warn("Trying to remove package folder: %s" % dest_folder)
                rmdir(dest_folder)
            except OSError as e:
                raise ConanException("%s\n\nCouldn't remove folder '%s', might be busy or open. "
                                     "Close any app using it, and retry" % (str(e), dest_folder))
            raise
        self._hook_manager.execute("post_download_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.id, remote=remote)

        return pref

    def search_recipes(self, remote, pattern=None, ignorecase=True):
        """
        Search exported conans information from remotes

        returns (dict str(ref): {packages_info}"""
        return self._call_remote(remote, "search", pattern, ignorecase)

    def search_packages(self, remote, ref, query):
        packages = self._call_remote(remote, "search_packages", ref, query)
        packages = filter_packages(query, packages)
        return packages

    def remove(self, ref, remote):
        """
        Removed conans or packages from remote
        """
        return self._call_remote(remote, "remove", ref)

    def remove_packages(self, ref, remove_ids, remote):
        """
        Removed conans or packages from remote
        """
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

    def _call_remote(self, remote, method, *argc, **argv):
        assert(isinstance(remote, Remote))
        self._auth_manager.remote = remote
        try:
            return getattr(self._auth_manager, method)(*argc, **argv)
        except ConnectionError as exc:
            raise ConanConnectionError("%s\n\nUnable to connect to %s=%s"
                                       % (str(exc), remote.name, remote.url))
        except ConanException as exc:
            exc.remote = remote
            raise
        except Exception as exc:
            logger.error(traceback.format_exc())
            raise ConanException(exc, remote=remote)


def is_package_snapshot_complete(snapshot):
    integrity = True
    for keyword in ["conaninfo", "conanmanifest", "conan_package"]:
        if not any(keyword in key for key in snapshot):
            integrity = False
            break
    return integrity


def check_compressed_files(tgz_name, files):
    bare_name = os.path.splitext(tgz_name)[0]
    for f in files:
        if f == tgz_name:
            continue
        if bare_name == os.path.splitext(f)[0]:
            raise ConanException("This Conan version is not prepared to handle '%s' file format. "
                                 "Please upgrade conan client." % f)


def unzip_and_get_files(files, destination_dir, tgz_name, output):
    """Moves all files from package_files, {relative_name: tmp_abs_path}
    to destination_dir, unzipping the "tgz_name" if found"""

    tgz_file = files.pop(tgz_name, None)
    check_compressed_files(tgz_name, files)
    if tgz_file:
        uncompress_file(tgz_file, destination_dir, output=output)
        os.remove(tgz_file)


def uncompress_file(src_path, dest_folder, output):
    t1 = time.time()
    try:
        with progress_bar.open_binary(src_path, desc="Decompressing %s" % os.path.basename(src_path),
                                      output=output) as file_handler:
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
