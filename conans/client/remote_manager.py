import os
import shutil
import tarfile
import time
import traceback

from requests.exceptions import ConnectionError

from conans.errors import ConanException, ConanConnectionError, NotFoundException
from conans.model.manifest import gather_files
from conans.paths import PACKAGE_TGZ_NAME, CONANINFO, CONAN_MANIFEST, CONANFILE, EXPORT_TGZ_NAME,\
    rm_conandir, EXPORT_SOURCES_TGZ_NAME, EXPORT_SOURCES_DIR
from conans.util.files import gzopen_without_timestamps
from conans.util.files import tar_extract, rmdir, exception_message_safe, mkdir
from conans.util.files import touch
from conans.util.log import logger
from conans.util.tracer import log_package_upload, log_recipe_upload,\
    log_recipe_download, log_package_download, log_recipe_sources_download, log_uncompressed_file, log_compressed_files


class RemoteManager(object):
    """ Will handle the remotes to get conans, packages etc """

    def __init__(self, client_cache, remote_client, output):
        self._client_cache = client_cache
        self._output = output
        self._remote_client = remote_client

    def upload_recipe(self, conan_reference, remote, retry, retry_wait, ignore_deleted_file,
                      skip_upload=False):
        """Will upload the conans to the first remote"""

        t1 = time.time()
        export_folder = self._client_cache.export(conan_reference)
        files, symlinks = gather_files(export_folder)

        if CONANFILE not in files or CONAN_MANIFEST not in files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(conan_reference))
        the_files = compress_recipe_files(files, symlinks, export_folder, self._output)
        if skip_upload:
            return None

        ret = self._call_remote(remote, "upload_recipe", conan_reference, the_files,
                                retry, retry_wait, ignore_deleted_file)
        duration = time.time() - t1
        log_recipe_upload(conan_reference, duration, the_files, remote)
        msg = "Uploaded conan recipe '%s' to '%s'" % (str(conan_reference), remote.name)
        # FIXME: server dependent
        if remote.url == "https://server.conan.io":
            msg += ": https://www.conan.io/source/%s" % "/".join(conan_reference)
        else:
            msg += ": %s" % remote.url
        self._output.info(msg)
        return ret

    def upload_package(self, package_reference, remote, retry, retry_wait, skip_upload=False):
        """Will upload the package to the first remote"""
        t1 = time.time()
        # existing package, will use short paths if defined
        package_folder = self._client_cache.package(package_reference, short_paths=None)
        # Get all the files in that directory
        files, symlinks = gather_files(package_folder)

        self._output.rewrite_line("Checking package integrity...")
        if CONANINFO not in files or CONAN_MANIFEST not in files:
            logger.error("Missing info or manifest in uploading files: %s" % (str(files)))
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))

        logger.debug("====> Time remote_manager build_files_set : %f" % (time.time() - t1))

        # If package has been modified remove tgz to regenerate it
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
        logger.debug("====> Time remote_manager check package integrity : %f" % (time.time() - t1))
        the_files = compress_package_files(files, symlinks, package_folder, self._output)
        if not skip_upload:

            tmp = self._call_remote(remote, "upload_package", package_reference, the_files,
                                    retry, retry_wait)

            duration = time.time() - t1
            log_package_upload(package_reference, duration, the_files, remote)
            logger.debug("====> Time remote_manager upload_package: %f" % duration)
            return tmp
        else:
            return None

    def get_conan_digest(self, conan_reference, remote):
        """
        Read ConanDigest from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (ConanDigest, remote_name)"""
        return self._call_remote(remote, "get_conan_digest", conan_reference)

    def get_package_digest(self, package_reference, remote):
        """
        Read ConanDigest from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (ConanDigest, remote_name)"""
        return self._call_remote(remote, "get_package_digest", package_reference)

    def get_package_info(self, package_reference, remote):
        """
        Read a package ConanInfo from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (ConanInfo, remote_name)"""
        return self._call_remote(remote, "get_package_info", package_reference)

    def get_recipe(self, conan_reference, dest_folder, remote):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""
        rmdir(dest_folder)  # Remove first the destination folder
        t1 = time.time()

        def filter_function(urls):
            if CONANFILE not in list(urls.keys()):
                raise NotFoundException("Conan '%s' doesn't have a %s!"
                                        % (conan_reference, CONANFILE))
            urls.pop(EXPORT_SOURCES_TGZ_NAME, None)
            return urls

        zipped_files = self._call_remote(remote, "get_recipe", conan_reference, dest_folder,
                                         filter_function)
        duration = time.time() - t1
        log_recipe_download(conan_reference, duration, remote, zipped_files)

        unzip_and_get_files(zipped_files, dest_folder, EXPORT_TGZ_NAME)
        # Make sure that the source dir is deleted
        rm_conandir(self._client_cache.source(conan_reference))
        for dirname, _, filenames in os.walk(dest_folder):
            for fname in filenames:
                touch(os.path.join(dirname, fname))

    def get_recipe_sources(self, conan_reference, export_folder, remote):
        t1 = time.time()

        def filter_function(urls):
            file_url = urls.get(EXPORT_SOURCES_TGZ_NAME)
            if file_url:
                urls = {EXPORT_SOURCES_TGZ_NAME: file_url}
            else:
                return None
            return urls

        zipped_files = self._call_remote(remote, "get_recipe",
                                         conan_reference, export_folder, filter_function)
        duration = time.time() - t1
        log_recipe_sources_download(conan_reference, duration, remote, zipped_files)

        sources_folder = os.path.join(export_folder, EXPORT_SOURCES_DIR)
        if not zipped_files:
            mkdir(sources_folder)  # create the folder even if no source files
            return

        unzip_and_get_files(zipped_files, export_folder, EXPORT_SOURCES_TGZ_NAME)
        for dirname, _, filenames in os.walk(sources_folder):
            for fname in filenames:
                touch(os.path.join(dirname, fname))

    def get_package(self, package_reference, dest_folder, remote):
        """
        Read the conans package from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""
        rm_conandir(dest_folder)  # Remove first the destination folder
        t1 = time.time()
        zipped_files = self._call_remote(remote, "get_package", package_reference, dest_folder)
        duration = time.time() - t1
        log_package_download(package_reference, duration, remote, zipped_files)
        unzip_and_get_files(zipped_files, dest_folder, PACKAGE_TGZ_NAME)
        # Issue #214 https://github.com/conan-io/conan/issues/214
        for dirname, _, filenames in os.walk(dest_folder):
            for fname in filenames:
                touch(os.path.join(dirname, fname))

    def search(self, remote, pattern=None, ignorecase=True):
        """
        Search exported conans information from remotes

        returns (dict str(conan_ref): {packages_info}"""
        return self._call_remote(remote, "search", pattern, ignorecase)

    def search_packages(self, remote, reference, query):
        return self._call_remote(remote, "search_packages", reference, query)

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

    def authenticate(self, remote, name, password):
        return self._call_remote(remote, 'authenticate', name, password)

    def _call_remote(self, remote, method, *argc, **argv):
        self._remote_client.remote = remote
        try:
            return getattr(self._remote_client, method)(*argc, **argv)
        except ConnectionError as exc:
            raise ConanConnectionError("%s\n\nUnable to connect to %s=%s"
                                       % (str(exc), remote.name, remote.url))
        except ConanException as exc:
            raise exc.__class__("%s. [Remote: %s]" % (exception_message_safe(exc), remote.name))
        except Exception as exc:
            logger.error(traceback.format_exc())
            raise ConanException(exc)


def compress_recipe_files(files, symlinks, dest_folder, output):
    # This is the minimum recipe
    result = {CONANFILE: files.pop(CONANFILE),
              CONAN_MANIFEST: files.pop(CONAN_MANIFEST)}

    export_tgz_path = files.pop(EXPORT_TGZ_NAME, None)
    sources_tgz_path = files.pop(EXPORT_SOURCES_TGZ_NAME, None)

    def add_tgz(tgz_name, tgz_path, msg):
        if tgz_path:
            result[tgz_name] = tgz_path
        else:
            if tgz_name == EXPORT_TGZ_NAME:
                tgz_files = {f: path for f, path in files.items()
                             if not f.startswith(EXPORT_SOURCES_DIR)}
            else:
                tgz_files = {f: path for f, path in files.items()
                             if f.startswith(EXPORT_SOURCES_DIR)}
            if tgz_files:
                output.rewrite_line(msg)
                tgz_path = compress_files(tgz_files, symlinks, tgz_name, dest_folder)
                result[tgz_name] = tgz_path

    add_tgz(EXPORT_TGZ_NAME, export_tgz_path, "Compressing recipe...")
    add_tgz(EXPORT_SOURCES_TGZ_NAME, sources_tgz_path, "Compressing recipe sources...")

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


def compress_files(files, symlinks, name, dest_dir):
    """Compress the package and returns the new dict (name => content) of files,
    only with the conanXX files and the compressed file"""
    t1 = time.time()
    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    with open(tgz_path, "wb") as tgz_handle:
        # tgz_contents = BytesIO()
        tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle)

        for filename, dest in symlinks.items():
            info = tarfile.TarInfo(name=filename)
            info.type = tarfile.SYMTYPE
            info.linkname = dest
            tgz.addfile(tarinfo=info)

        for filename, abs_path in files.items():
            info = tarfile.TarInfo(name=filename)
            info.size = os.stat(abs_path).st_size
            info.mode = os.stat(abs_path).st_mode
            if os.path.islink(abs_path):
                info.type = tarfile.SYMTYPE
                info.linkname = os.readlink(abs_path)  # @UndefinedVariable
                tgz.addfile(tarinfo=info)
            else:
                with open(abs_path, 'rb') as file_handler:
                    tgz.addfile(tarinfo=info, fileobj=file_handler)

        tgz.close()

    duration = time.time() - t1
    log_compressed_files(files, duration, tgz_path)

    return tgz_path


def unzip_and_get_files(files, destination_dir, tgz_name):
    """Moves all files from package_files, {relative_name: tmp_abs_path}
    to destination_dir, unzipping the "tgz_name" if found"""

    tgz_file = files.pop(tgz_name, None)
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
        except Exception as e:
            error_msg += "Folder not removed, files/package might be damaged, remove manually"
        raise ConanException(error_msg)

    duration = time.time() - t1
    log_uncompressed_file(src_path, duration, dest_folder)
