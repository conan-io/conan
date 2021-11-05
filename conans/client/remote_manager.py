import os
import shutil
import time
import traceback

from requests.exceptions import ConnectionError

from conans.cli.output import ConanOutput
from conans.client.cache.remote_registry import Remote
from conans.errors import ConanConnectionError, ConanException, NotFoundException, \
    PackageNotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.search.search import filter_packages
from conans.util import progress_bar
from conans.util.env_reader import get_env
from conans.util.files import make_read_only, mkdir, tar_extract, touch_folder, md5sum, sha1sum, \
    rmdir
from conans.util.log import logger
# FIXME: Eventually, when all output is done, tracer functions should be moved to the recorder class
from conans.util.tracer import (log_package_download,
                                log_recipe_download, log_recipe_sources_download,
                                log_uncompressed_file)

CONAN_REQUEST_HEADER_SETTINGS = 'Conan-PkgID-Settings'
CONAN_REQUEST_HEADER_OPTIONS = 'Conan-PkgID-Options'


def _headers_for_info(info):
    if not info:
        return None

    r = {}
    settings = info.full_settings.as_list()
    if settings:
        settings = ['{}={}'.format(*it) for it in settings]
        r.update({CONAN_REQUEST_HEADER_SETTINGS: ';'.join(settings)})

    options = info.options._package_options.items()  # FIXME
    if options:
        options = filter(lambda u: u[0] in ['shared', 'fPIC', 'header_only'], options)
        options = ['{}={}'.format(*it) for it in options]
        r.update({CONAN_REQUEST_HEADER_OPTIONS: ';'.join(options)})
    return r


class RemoteManager(object):
    """ Will handle the remotes to get recipes, packages etc """

    def __init__(self, cache, auth_manager, hook_manager):
        self._cache = cache
        self._output = ConanOutput()
        self._auth_manager = auth_manager
        self._hook_manager = hook_manager

    def check_credentials(self, remote):
        self._call_remote(remote, "check_credentials")

    def get_recipe_snapshot(self, ref, remote):
        assert ref.revision, "get_recipe_snapshot requires revision"
        return self._call_remote(remote, "get_recipe_snapshot", ref)

    def upload_recipe(self, ref, files_to_upload, deleted, remote, retry, retry_wait):
        assert isinstance(ref, RecipeReference)
        assert ref.revision, "upload_recipe requires RREV"
        self._call_remote(remote, "upload_recipe", ref, files_to_upload, deleted,
                          retry, retry_wait)

    def upload_package(self, pref, files_to_upload, remote, retry, retry_wait):
        assert pref.ref.revision, "upload_package requires RREV"
        assert pref.revision, "upload_package requires PREV"
        self._call_remote(remote, "upload_package", pref, files_to_upload, retry, retry_wait)

    # FIXME: this method returns the latest package revision with the time or if a prev is specified
    #  it returns that prev if it exists in the server with the time
    def get_latest_package_revision_with_time(self, pref, remote, info=None):
        headers = _headers_for_info(info)
        revisions = self._call_remote(remote, "get_package_revisions", pref, headers=headers)
        timestamp = revisions[0].get("time")
        ref = PkgReference(pref.ref, pref.package_id, revisions[0].get("revision"),
                           timestamp=timestamp)
        return ref

    def get_recipe(self, ref, remote):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""

        self._hook_manager.execute("pre_download_recipe", reference=ref, remote=remote)

        ref = self._resolve_latest_ref(ref, remote)

        layout = self._cache.get_or_create_ref_layout(ref)

        layout.export_remove()

        t1 = time.time()
        download_export = layout.download_export()
        zipped_files = self._call_remote(remote, "get_recipe", ref, download_export)
        remote_revisions = self._call_remote(remote, "get_recipe_revisions", ref)
        ref_time = remote_revisions[0].get("time")
        duration = time.time() - t1
        log_recipe_download(ref, duration, remote.name, zipped_files)

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
        touch_folder(export_folder)
        conanfile_path = layout.conanfile()

        self._hook_manager.execute("post_download_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        return ref, ref_time

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
        touch_folder(export_sources_folder)

    def get_package(self, conanfile, pref, remote):
        ref_layout = self._cache.ref_layout(pref.ref)
        conanfile_path = ref_layout.conanfile()
        self._hook_manager.execute("pre_download_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.package_id, remote=remote,
                                   conanfile=conanfile)

        conanfile.output.info("Retrieving package %s from remote '%s' " % (pref.package_id,
                                                                           remote.name))
        latest_prev, _ = self.get_latest_package_revision(pref, remote)

        pkg_layout = self._cache.get_or_create_pkg_layout(latest_prev)

        pkg_layout.package_remove()  # Remove first the destination folder
        with pkg_layout.set_dirty_context_manager():
            info = getattr(conanfile, 'info', None)
            self._get_package(pkg_layout, pref, remote, conanfile.output, info=info)

        self._hook_manager.execute("post_download_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.package_id, remote=remote,
                                   conanfile=conanfile)

    def _get_package(self, layout, pref, remote, scoped_output, info):
        t1 = time.time()
        try:
            headers = _headers_for_info(info)
            pref = self._resolve_latest_pref(pref, remote, headers=headers)

            download_pkg_folder = layout.download_package()
            # Download files to the pkg_tgz folder, not to the final one
            zipped_files = self._call_remote(remote, "get_package", pref, download_pkg_folder)

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
            # Issue #214 https://github.com/conan-io/conan/issues/214
            touch_folder(package_folder)
            if get_env("CONAN_READ_ONLY_CACHE", False):
                make_read_only(package_folder)

            scoped_output.success('Package installed %s' % pref.package_id)
            scoped_output.info("Downloaded package revision %s" % pref.revision)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        except BaseException as e:
            scoped_output.error("Exception while getting package: %s" % str(pref.package_id))
            scoped_output.error("Exception: %s %s" % (type(e), str(e)))
            raise

    def search_recipes(self, remote, pattern, ignorecase=True):
        """
        returns (dict str(ref): {packages_info}
        """
        # TODO: Remove the ignorecase param. It's not used anymore, we're keeping it
        # to avoid some test crashes

        return self._call_remote(remote, "search", pattern)

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

    def get_package_revisions(self, pref, remote, headers=None):
        revisions = self._call_remote(remote, "get_package_revisions", pref, headers=headers)
        return revisions

    def get_latest_recipe_revision(self, ref, remote):
        revision, rev_time = self._call_remote(remote, "get_latest_recipe_revision", ref)
        return revision, rev_time

    def get_latest_package_revision(self, pref, remote, headers=None):
        pkgref, rev_time = self._call_remote(remote, "get_latest_package_revision", pref,
                                             headers=headers)
        return pkgref, rev_time

    # FIXME: this method returns the latest recipe revision with the time or if a rrev is specified
    #  it returns that rrev if it exists in the server with the time
    def get_latest_recipe_revision_with_time(self, ref, remote):
        revisions = self._call_remote(remote, "get_recipe_revisions", ref)
        return ref.copy_with_rev(revisions[0].get("revision")), revisions[0].get("time")

    def _resolve_latest_ref(self, ref, remote):
        if ref.revision is None:
            ref, _ = self.get_latest_recipe_revision(ref, remote)
        return ref

    def _resolve_latest_pref(self, pref, remote, headers):
        if pref.revision is None:
            pref, _ = self.get_latest_package_revision(pref, remote, headers=headers)
        return pref

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
            logger.error(traceback.format_exc())
            raise ConanException(exc, remote=remote)


def calc_files_checksum(files):
    return {file_name: {"md5": md5sum(path), "sha1": sha1sum(path)}
            for file_name, path in files.items()}


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
        with progress_bar.open_binary(src_path, "Decompressing "
                                                "%s" % os.path.basename(src_path)) as file_handler:
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
