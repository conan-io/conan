import os
import stat
import tarfile
import traceback

import shutil
import time
from requests.exceptions import ConnectionError

from conans.client.remote_registry import Remote
from conans.errors import ConanException, ConanConnectionError, NotFoundException
from conans.model.manifest import gather_files
from conans.paths import PACKAGE_TGZ_NAME, CONANINFO, CONAN_MANIFEST, CONANFILE, EXPORT_TGZ_NAME, \
    rm_conandir, EXPORT_SOURCES_TGZ_NAME, EXPORT_SOURCES_DIR_OLD

from conans.util.files import gzopen_without_timestamps, is_dirty,\
    make_read_only, set_dirty, clean_dirty

from conans.util.files import tar_extract, rmdir, exception_message_safe, mkdir
from conans.util.files import touch_folder
from conans.util.log import logger
# FIXME: Eventually, when all output is done, tracer functions should be moved to the recorder class
from conans.util.tracer import (log_package_upload, log_recipe_upload,
                                log_recipe_sources_download,
                                log_uncompressed_file, log_compressed_files, log_recipe_download,
                                log_package_download)

from conans.client.source import merge_directories
from conans.util.env_reader import get_env
from conans.search.search import filter_packages


class RemoteManager(object):
    """ Will handle the remotes to get recipes, packages etc """

    def __init__(self, client_cache, auth_manager, output):
        self._client_cache = client_cache
        self._output = output
        self._auth_manager = auth_manager

    def upload_recipe(self, conan_reference, remote, retry, retry_wait, ignore_deleted_file,
                      skip_upload=False, no_overwrite=None):
        """Will upload the conans to the first remote"""
        t1 = time.time()
        export_folder = self._client_cache.export(conan_reference)

        for f in (EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME):
            tgz_path = os.path.join(export_folder, f)
            if is_dirty(tgz_path):
                self._output.warn("%s: Removing %s, marked as dirty" % (str(conan_reference), f))
                os.remove(tgz_path)
                clean_dirty(tgz_path)

        files, symlinks = gather_files(export_folder)
        if CONANFILE not in files or CONAN_MANIFEST not in files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(conan_reference))
        export_src_folder = self._client_cache.export_sources(conan_reference, short_paths=None)
        src_files, src_symlinks = gather_files(export_src_folder)
        the_files = _compress_recipe_files(files, symlinks, src_files, src_symlinks, export_folder,
                                           self._output)
        if skip_upload:
            return None

        ret, new_ref = self._call_remote(remote, "upload_recipe", conan_reference, the_files, retry,
                                         retry_wait, ignore_deleted_file, no_overwrite)
        duration = time.time() - t1
        log_recipe_upload(new_ref, duration, the_files, remote.name)
        if ret:
            msg = "Uploaded conan recipe '%s' to '%s'" % (str(new_ref), remote.name)
            url = remote.url.replace("https://api.bintray.com/conan", "https://bintray.com")
            msg += ": %s" % url
        else:
            msg = "Recipe is up to date, upload skipped"
        self._output.info(msg)
        return new_ref

    def _package_integrity_check(self, package_reference, files, package_folder):
        # If package has been modified remove tgz to regenerate it
        self._output.rewrite_line("Checking package integrity...")
        read_manifest, expected_manifest = self._client_cache.package_manifests(package_reference)

        if read_manifest != expected_manifest:
            self._output.writeln("")
            diff = read_manifest.difference(expected_manifest)
            for fname, (h1, h2) in diff.items():
                self._output.warn("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                  % (fname, h1, h2))

            if PACKAGE_TGZ_NAME in files:
                try:
                    tgz_path = os.path.join(package_folder, PACKAGE_TGZ_NAME)
                    os.unlink(tgz_path)
                except Exception:
                    pass
            error_msg = os.linesep.join("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                        % (fname, h1, h2) for fname, (h1, h2) in diff.items())
            logger.error("Manifests doesn't match!\n%s" % error_msg)
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))
        else:
            self._output.rewrite_line("Package integrity OK!")
        self._output.writeln("")

    def upload_package(self, package_reference, remote, retry, retry_wait, skip_upload=False,
                       integrity_check=False, no_overwrite=None):
        """Will upload the package to the first remote"""
        t1 = time.time()
        # existing package, will use short paths if defined
        package_folder = self._client_cache.package(package_reference, short_paths=None)

        if is_dirty(package_folder):
            raise ConanException("Package %s is corrupted, aborting upload.\n"
                                 "Remove it with 'conan remove %s -p=%s'" % (package_reference,
                                                                             package_reference.conan,
                                                                             package_reference.package_id))
        tgz_path = os.path.join(package_folder, PACKAGE_TGZ_NAME)
        if is_dirty(tgz_path):
            self._output.warn("%s: Removing %s, marked as dirty" % (str(package_reference), PACKAGE_TGZ_NAME))
            os.remove(tgz_path)
            clean_dirty(tgz_path)
        # Get all the files in that directory
        files, symlinks = gather_files(package_folder)

        if CONANINFO not in files or CONAN_MANIFEST not in files:
            logger.error("Missing info or manifest in uploading files: %s" % (str(files)))
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))

        logger.debug("====> Time remote_manager build_files_set : %f" % (time.time() - t1))

        if integrity_check:
            self._package_integrity_check(package_reference, files, package_folder)
            logger.debug("====> Time remote_manager check package integrity : %f"
                         % (time.time() - t1))

        the_files = compress_package_files(files, symlinks, package_folder, self._output)
        if skip_upload:
            return None

        tmp = self._call_remote(remote, "upload_package", package_reference, the_files,
                                retry, retry_wait, no_overwrite)
        duration = time.time() - t1
        log_package_upload(package_reference, duration, the_files, remote)
        logger.debug("====> Time remote_manager upload_package: %f" % duration)
        if not tmp:
            self._output.rewrite_line("Package is up to date, upload skipped")
            self._output.writeln("")

        return tmp

    def get_conan_manifest(self, conan_reference, remote):
        """
        Read ConanDigest from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (ConanDigest, remote_name)"""
        return self._call_remote(remote, "get_conan_manifest", conan_reference)

    def get_package_manifest(self, package_reference, remote):
        """
        Read ConanDigest from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (ConanDigest, remote_name)"""
        return self._call_remote(remote, "get_package_manifest", package_reference)

    def get_package_info(self, package_reference, remote):
        """
        Read a package ConanInfo from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (ConanInfo, remote_name)"""
        return self._call_remote(remote, "get_package_info", package_reference)

    def get_recipe(self, conan_reference, remote):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""
        dest_folder = self._client_cache.export(conan_reference)
        rmdir(dest_folder)

        t1 = time.time()
        zipped_files, conan_reference = self._call_remote(remote, "get_recipe", conan_reference,
                                                          dest_folder)
        duration = time.time() - t1
        log_recipe_download(conan_reference, duration, remote.name, zipped_files)

        unzip_and_get_files(zipped_files, dest_folder, EXPORT_TGZ_NAME)
        # Make sure that the source dir is deleted
        rm_conandir(self._client_cache.source(conan_reference))
        touch_folder(dest_folder)
        return conan_reference

    def get_recipe_sources(self, conan_reference, export_folder, export_sources_folder, remote):
        t1 = time.time()

        zipped_files = self._call_remote(remote, "get_recipe_sources", conan_reference,
                                         export_folder)
        if not zipped_files:
            mkdir(export_sources_folder)  # create the folder even if no source files
            return conan_reference

        duration = time.time() - t1
        log_recipe_sources_download(conan_reference, duration, remote.name, zipped_files)

        unzip_and_get_files(zipped_files, export_sources_folder, EXPORT_SOURCES_TGZ_NAME)
        c_src_path = os.path.join(export_sources_folder, EXPORT_SOURCES_DIR_OLD)
        if os.path.exists(c_src_path):
            merge_directories(c_src_path, export_sources_folder)
            rmdir(c_src_path)
        touch_folder(export_sources_folder)
        return conan_reference

    def get_package(self, package_reference, dest_folder, remote, output, recorder):
        package_id = package_reference.package_id
        output.info("Retrieving package %s from remote '%s' " % (package_id, remote.name))
        rm_conandir(dest_folder)  # Remove first the destination folder
        t1 = time.time()
        try:
            zipped_files = self._call_remote(remote, "get_package", package_reference, dest_folder)
            duration = time.time() - t1
            log_package_download(package_reference, duration, remote, zipped_files)
            unzip_and_get_files(zipped_files, dest_folder, PACKAGE_TGZ_NAME)
            # Issue #214 https://github.com/conan-io/conan/issues/214
            touch_folder(dest_folder)
            if get_env("CONAN_READ_ONLY_CACHE", False):
                make_read_only(dest_folder)
            recorder.package_downloaded(package_reference, remote.url)
            output.success('Package installed %s' % package_id)
        except NotFoundException:
            raise NotFoundException("Package binary '%s' not found in '%s'" % (package_reference, remote.name))
        except BaseException as e:
            output.error("Exception while getting package: %s" % str(package_reference.package_id))
            output.error("Exception: %s %s" % (type(e), str(e)))
            try:
                output.warn("Trying to remove package folder: %s" % dest_folder)
                rmdir(dest_folder)
            except OSError as e:
                raise ConanException("%s\n\nCouldn't remove folder '%s', might be busy or open. Close any app "
                                     "using it, and retry" % (str(e), dest_folder))
            raise

    def search_recipes(self, remote, pattern=None, ignorecase=True):
        """
        Search exported conans information from remotes

        returns (dict str(conan_ref): {packages_info}"""
        return self._call_remote(remote, "search", pattern, ignorecase)

    def search_packages(self, remote, reference, query):
        packages = self._call_remote(remote, "search_packages", reference, query)
        packages = filter_packages(query, packages)
        return packages

    def remove(self, conan_ref, remote):
        """
        Removed conans or packages from remote
        """
        return self._call_remote(remote, "remove", conan_ref)

    def remove_packages(self, conan_ref, remove_ids, remote):
        """
        Removed conans or packages from remote
        """
        return self._call_remote(remote, "remove_packages", conan_ref, remove_ids)

    def get_path(self, conan_ref, package_id, path, remote):
        return self._call_remote(remote, "get_path", conan_ref, package_id, path)

    def authenticate(self, remote, name, password):
        return self._call_remote(remote, 'authenticate', name, password)

    def _call_remote(self, remote, method, *argc, **argv):
        assert(isinstance(remote, Remote))
        self._auth_manager.remote = remote
        try:
            return getattr(self._auth_manager, method)(*argc, **argv)
        except ConnectionError as exc:
            raise ConanConnectionError("%s\n\nUnable to connect to %s=%s"
                                       % (str(exc), remote.name, remote.url))
        except ConanException as exc:
            raise exc.__class__("%s. [Remote: %s]" % (exception_message_safe(exc), remote.name))
        except Exception as exc:
            logger.error(traceback.format_exc())
            raise ConanException(exc)


def _compress_recipe_files(files, symlinks, src_files, src_symlinks, dest_folder, output):
    # This is the minimum recipe
    result = {CONANFILE: files.pop(CONANFILE),
              CONAN_MANIFEST: files.pop(CONAN_MANIFEST)}

    export_tgz_path = files.pop(EXPORT_TGZ_NAME, None)
    sources_tgz_path = files.pop(EXPORT_SOURCES_TGZ_NAME, None)

    def add_tgz(tgz_name, tgz_path, tgz_files, tgz_symlinks, msg):
        if tgz_path:
            result[tgz_name] = tgz_path
        elif tgz_files:
            output.rewrite_line(msg)
            tgz_path = compress_files(tgz_files, tgz_symlinks, tgz_name, dest_folder)
            result[tgz_name] = tgz_path

    add_tgz(EXPORT_TGZ_NAME, export_tgz_path, files, symlinks, "Compressing recipe...")
    add_tgz(EXPORT_SOURCES_TGZ_NAME, sources_tgz_path, src_files, src_symlinks,
            "Compressing recipe sources...")

    return result


def compress_package_files(files, symlinks, dest_folder, output):
    tgz_path = files.get(PACKAGE_TGZ_NAME)
    if not tgz_path:
        output.rewrite_line("Compressing package...")
        tgz_files = {f: path for f, path in files.items() if f not in [CONANINFO, CONAN_MANIFEST]}
        tgz_path = compress_files(tgz_files, symlinks, PACKAGE_TGZ_NAME, dest_dir=dest_folder)

    return {PACKAGE_TGZ_NAME: tgz_path,
            CONANINFO: files[CONANINFO],
            CONAN_MANIFEST: files[CONAN_MANIFEST]}


def check_compressed_files(tgz_name, files):
    bare_name = os.path.splitext(tgz_name)[0]
    for f in files:
        if f == tgz_name:
            continue
        if bare_name == os.path.splitext(f)[0]:
            raise ConanException("This Conan version is not prepared to handle '%s' file format. "
                                 "Please upgrade conan client." % f)


def compress_files(files, symlinks, name, dest_dir):
    t1 = time.time()
    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    set_dirty(tgz_path)
    with open(tgz_path, "wb") as tgz_handle:
        # tgz_contents = BytesIO()
        tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle)

        for filename, dest in sorted(symlinks.items()):
            info = tarfile.TarInfo(name=filename)
            info.type = tarfile.SYMTYPE
            info.linkname = dest
            tgz.addfile(tarinfo=info)

        mask = ~(stat.S_IWOTH | stat.S_IWGRP)
        for filename, abs_path in sorted(files.items()):
            info = tarfile.TarInfo(name=filename)
            info.size = os.stat(abs_path).st_size
            info.mode = os.stat(abs_path).st_mode & mask
            if os.path.islink(abs_path):
                info.type = tarfile.SYMTYPE
                info.linkname = os.readlink(abs_path)  # @UndefinedVariable
                tgz.addfile(tarinfo=info)
            else:
                with open(abs_path, 'rb') as file_handler:
                    tgz.addfile(tarinfo=info, fileobj=file_handler)

        tgz.close()

    clean_dirty(tgz_path)
    duration = time.time() - t1
    log_compressed_files(files, duration, tgz_path)

    return tgz_path


def unzip_and_get_files(files, destination_dir, tgz_name):
    """Moves all files from package_files, {relative_name: tmp_abs_path}
    to destination_dir, unzipping the "tgz_name" if found"""

    tgz_file = files.pop(tgz_name, None)
    check_compressed_files(tgz_name, files)
    if tgz_file:
        uncompress_file(tgz_file, destination_dir)
        os.remove(tgz_file)


def uncompress_file(src_path, dest_folder):
    t1 = time.time()
    try:
        with open(src_path, 'rb') as file_handler:
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
