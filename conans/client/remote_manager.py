import os
import shutil
import time
from typing import List

from requests.exceptions import ConnectionError

from conan.api.output import ConanOutput
from conan.internal.cache.conan_reference_layout import METADATA
from conans.client.cache.remote_registry import Remote
from conans.client.pkg_sign import PkgSignaturesPlugin
from conans.errors import ConanConnectionError, ConanException, NotFoundException, \
    PackageNotFoundException
from conans.model.info import load_binary_info
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.files import rmdir
from conans.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.util.files import mkdir, tar_extract

# FIXME: Eventually, when all output is done, tracer functions should be moved to the recorder class
from conans.util.tracer import (log_package_download,
                                log_recipe_download, log_recipe_sources_download,
                                log_uncompressed_file)


class RemoteManager(object):
    """ Will handle the remotes to get recipes, packages etc """

    def __init__(self, cache, auth_manager, hook_manager):
        self._cache = cache
        self._auth_manager = auth_manager
        self._signer = PkgSignaturesPlugin(cache)

    def check_credentials(self, remote):
        self._call_remote(remote, "check_credentials")

    def get_recipe_snapshot(self, ref, remote):
        assert ref.revision, "get_recipe_snapshot requires revision"
        return self._call_remote(remote, "get_recipe_snapshot", ref)

    def upload_recipe(self, ref, files_to_upload, deleted, remote):
        assert isinstance(ref, RecipeReference)
        assert ref.revision, "upload_recipe requires RREV"
        self._call_remote(remote, "upload_recipe", ref, files_to_upload, deleted)

    def upload_package(self, pref, files_to_upload, remote):
        assert pref.ref.revision, "upload_package requires RREV"
        assert pref.revision, "upload_package requires PREV"
        self._call_remote(remote, "upload_package", pref, files_to_upload)

    def get_recipe(self, ref, remote):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""

        assert ref.revision, "get_recipe without revision specified"

        layout = self._cache.get_or_create_ref_layout(ref)
        layout.export_remove()

        t1 = time.time()
        download_export = layout.download_export()
        zipped_files = self._call_remote(remote, "get_recipe", ref, download_export)
        remote_refs = self._call_remote(remote, "get_recipe_revisions_references", ref)
        ref_time = remote_refs[0].timestamp
        ref.timestamp = ref_time
        duration = time.time() - t1
        log_recipe_download(ref, duration, remote.name, zipped_files)
        # filter metadata files
        # This could be also optimized in the download, avoiding downloading them, for performance
        zipped_files = {k: v for k, v in zipped_files.items() if not k.startswith(METADATA)}
        self._signer.verify(ref, download_export)
        export_folder = layout.export()
        tgz_file = zipped_files.pop(EXPORT_TGZ_NAME, None)

        check_compressed_files(EXPORT_TGZ_NAME, zipped_files)
        if tgz_file:
            uncompress_file(tgz_file, export_folder)
        mkdir(export_folder)
        for file_name, file_path in zipped_files.items():  # copy CONANFILE
            shutil.move(file_path, os.path.join(export_folder, file_name))

        # Make sure that the source dir is deleted
        rmdir(layout.source())

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
        uncompress_file(tgz_file, export_sources_folder)

    def get_package(self, conanfile, pref, remote):
        conanfile.output.info("Retrieving package %s from remote '%s' " % (pref.package_id,
                                                                           remote.name))

        assert pref.revision is not None

        pkg_layout = self._cache.get_or_create_pkg_layout(pref)
        pkg_layout.package_remove()  # Remove first the destination folder
        with pkg_layout.set_dirty_context_manager():
            self._get_package(pkg_layout, pref, remote, conanfile.output)

    def _get_package(self, layout, pref, remote, scoped_output):
        t1 = time.time()
        try:
            assert pref.revision is not None

            download_pkg_folder = layout.download_package()
            # Download files to the pkg_tgz folder, not to the final one
            zipped_files = self._call_remote(remote, "get_package", pref, download_pkg_folder)
            zipped_files = {k: v for k, v in zipped_files.items() if not k.startswith(METADATA)}
            self._signer.verify(pref, download_pkg_folder)
            duration = time.time() - t1
            log_package_download(pref, duration, remote, zipped_files)

            tgz_file = zipped_files.pop(PACKAGE_TGZ_NAME, None)
            check_compressed_files(PACKAGE_TGZ_NAME, zipped_files)
            package_folder = layout.package()
            if tgz_file:  # This must happen always, but just in case
                # TODO: The output could be changed to the package one, but
                uncompress_file(tgz_file, package_folder)
            mkdir(package_folder)  # Just in case it doesn't exist, because uncompress did nothing
            for file_name, file_path in zipped_files.items():  # copy CONANINFO and CONANMANIFEST
                shutil.move(file_path, os.path.join(package_folder, file_name))

            scoped_output.success('Package installed %s' % pref.package_id)
            scoped_output.info("Downloaded package revision %s" % pref.revision)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        except BaseException as e:
            scoped_output.error("Exception while getting package: %s" % str(pref.package_id))
            scoped_output.error("Exception: %s %s" % (type(e), str(e)))
            raise

    def search_recipes(self, remote, pattern):
        return self._call_remote(remote, "search", pattern)

    def search_packages(self, remote, ref):
        packages = self._call_remote(remote, "search_packages", ref)
        # Avoid serializing conaninfo in server side
        packages = {PkgReference(ref, pid): load_binary_info(data["content"])
                    if "content" in data else data
                    for pid, data in packages.items() if not data.get("recipe_hash")}
        return packages

    def remove_recipe(self, ref, remote):
        return self._call_remote(remote, "remove_recipe", ref)

    def remove_packages(self, prefs, remote):
        return self._call_remote(remote, "remove_packages", prefs)

    def remove_all_packages(self, ref, remote):
        return self._call_remote(remote, "remove_all_packages", ref)

    def authenticate(self, remote, name, password):
        return self._call_remote(remote, 'authenticate', name, password)

    def get_recipe_revisions_references(self, ref, remote):
        assert ref.revision is None, "get_recipe_revisions_references of a reference with revision"
        return self._call_remote(remote, "get_recipe_revisions_references", ref)

    def get_package_revisions_references(self, pref, remote, headers=None) -> List[PkgReference]:
        assert pref.revision is None, "get_package_revisions_references of a reference with revision"
        return self._call_remote(remote, "get_package_revisions_references", pref, headers=headers)

    def get_latest_recipe_reference(self, ref, remote):
        assert ref.revision is None, "get_latest_recipe_reference of a reference with revision"
        return self._call_remote(remote, "get_latest_recipe_reference", ref)

    def get_latest_package_reference(self, pref, remote) -> PkgReference:
        assert pref.revision is None, "get_latest_package_reference of a reference with revision"
        return self._call_remote(remote, "get_latest_package_reference", pref, headers=None)

    def get_recipe_revision_reference(self, ref, remote) -> bool:
        assert ref.revision is not None, "recipe_exists needs a revision"
        return self._call_remote(remote, "get_recipe_revision_reference", ref)

    def get_package_revision_reference(self, pref, remote) -> bool:
        assert pref.revision is not None, "get_package_revision_reference needs a revision"
        return self._call_remote(remote, "get_package_revision_reference", pref)

    def _call_remote(self, remote, method, *args, **kwargs):
        assert (isinstance(remote, Remote))
        if remote.disabled:
            raise ConanException("Remote '%s' is disabled" % remote.name)
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
            raise ConanException(exc, remote=remote)


# TODO: Consider removing this, we are not changing the compression format
def check_compressed_files(tgz_name, files):
    bare_name = os.path.splitext(tgz_name)[0]
    for f in files:
        if f == tgz_name:
            continue
        if bare_name == os.path.splitext(f)[0]:
            raise ConanException("This Conan version is not prepared to handle '%s' file format. "
                                 "Please upgrade conan client." % f)


def uncompress_file(src_path, dest_folder):
    t1 = time.time()
    try:
        ConanOutput().info("Decompressing %s" % os.path.basename(src_path))
        with open(src_path, mode='rb') as file_handler:
            tar_extract(file_handler, dest_folder)
    except Exception as e:
        error_msg = "Error while extracting downloaded file '%s' to %s\n%s\n"\
                    % (src_path, dest_folder, str(e))
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
