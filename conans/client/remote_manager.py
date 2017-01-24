import os
import shutil
import tarfile
import time
import traceback

from requests.exceptions import ConnectionError

from conans.errors import ConanException, ConanConnectionError
from conans.util.files import tar_extract, relative_dirs, rmdir,\
    exception_message_safe, save, load
from conans.util.log import logger
from conans.paths import PACKAGE_TGZ_NAME, CONANINFO, CONAN_MANIFEST, CONANFILE, EXPORT_TGZ_NAME,\
    rm_conandir, EXPORT_SOURCES_TGZ_NAME, EXPORT_SOURCES_DIR
from conans.util.files import gzopen_without_timestamps
from conans.util.files import touch
from conans.model.manifest import discarded_file
from conans.util.tracer import log_package_upload, log_recipe_upload,\
    log_recipe_download, log_package_download


class RemoteManager(object):
    """ Will handle the remotes to get conans, packages etc """

    def __init__(self, client_cache, remote_client, output):
        self._client_cache = client_cache
        self._output = output
        self._remote_client = remote_client

    def upload_conan(self, conan_reference, remote, retry, retry_wait):
        """Will upload the conans to the first remote"""

        t1 = time.time()
        export_folder = self._client_cache.export(conan_reference)
        # make sure that the recipe is complete, with the sources
        self.get_recipe_sources(conan_reference, export_folder, remote)
        rel_files = relative_dirs(export_folder)
        the_files = {filename: os.path.join(export_folder, filename) for filename in rel_files}

        if CONANFILE not in rel_files or CONAN_MANIFEST not in rel_files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(conan_reference))

        sources_folder = os.path.join(export_folder, EXPORT_SOURCES_DIR)
        if os.path.exists(sources_folder):
            source_files = {k: v for k, v in the_files.items() if k.startswith(EXPORT_SOURCES_DIR)}
            the_files = {k: v for k, v in the_files.items() if not k.startswith(EXPORT_SOURCES_DIR)}

        # FIXME: Check modified exports by hand?
        the_files = compress_conan_files(the_files, export_folder, EXPORT_TGZ_NAME,
                                         CONANFILE, self._output)

        if os.path.exists(sources_folder):
            sources_tgz = source_files.get(EXPORT_SOURCES_TGZ_NAME)
            if not sources_tgz:
                # zip
                new_files = compress_files(source_files, EXPORT_SOURCES_TGZ_NAME, excluded=[],
                                           dest_dir=sources_folder)
                sources_tgz = new_files[EXPORT_SOURCES_TGZ_NAME]
            the_files[EXPORT_SOURCES_TGZ_NAME] = sources_tgz

        ret = self._call_remote(remote, "upload_conan", conan_reference, the_files,
                                retry, retry_wait)
        duration = time.time() - t1
        log_recipe_upload(conan_reference, duration, the_files)
        msg = "Uploaded conan recipe '%s' to '%s'" % (str(conan_reference), remote.name)
        # FIXME: server dependent
        if remote.url == "https://server.conan.io":
            msg += ": https://www.conan.io/source/%s" % "/".join(conan_reference)
        else:
            msg += ": %s" % remote.url
        self._output.info(msg)

        return ret

    def upload_package(self, package_reference, remote, retry, retry_wait):
        """Will upload the package to the first remote"""
        t1 = time.time()
        # existing package, will use short paths if defined
        package_folder = self._client_cache.package(package_reference, short_paths=None)
        # Get all the files in that directory
        rel_files = relative_dirs(package_folder)

        self._output.rewrite_line("Checking package integrity...")
        if CONANINFO not in rel_files or CONAN_MANIFEST not in rel_files:
            logger.error("Missing info or manifest in uploading files: %s" % (str(rel_files)))
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))

        the_files = {filename: os.path.join(package_folder, filename) for filename in rel_files if
                     not discarded_file(filename)}
        logger.debug("====> Time remote_manager build_files_set : %f" % (time.time() - t1))

        # If package has been modified remove tgz to regenerate it
        read_manifest, expected_manifest = self._client_cache.package_manifests(package_reference)

        if read_manifest is None or read_manifest.file_sums != expected_manifest.file_sums:
            self._output.writeln("")
            for fname in read_manifest.file_sums.keys():
                if read_manifest.file_sums[fname] != expected_manifest.file_sums[fname]:
                    self._output.warn("Mismatched checksum for file %s (checksum: %s, expected: %s)" %
                                      (fname, read_manifest.file_sums[fname], expected_manifest.file_sums[fname]))

            if PACKAGE_TGZ_NAME in the_files:
                try:
                    tgz_path = os.path.join(package_folder, PACKAGE_TGZ_NAME)
                    os.unlink(tgz_path)
                except Exception:
                    pass
            logger.error("Manifests doesn't match!: %s != %s" % (str(read_manifest.file_sums),
                                                                 str(expected_manifest.file_sums)))
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))
        else:
            self._output.rewrite_line("Package integrity OK!")
        self._output.writeln("")
        logger.debug("====> Time remote_manager check package integrity : %f" % (time.time() - t1))

        the_files = compress_conan_files(the_files, package_folder, PACKAGE_TGZ_NAME,
                                         CONANINFO, self._output)

        tmp = self._call_remote(remote, "upload_package", package_reference, the_files,
                                retry, retry_wait)
        duration = time.time() - t1
        log_package_upload(package_reference, duration, the_files)
        logger.debug("====> Time remote_manager upload_package: %f" % (duration))
        return tmp

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
        zipped_files = self._call_remote(remote, "get_recipe", conan_reference, dest_folder)
        duration = time.time() - t1
        log_recipe_download(conan_reference, duration, remote, zipped_files)

        files = unzip_and_get_files(zipped_files, dest_folder, EXPORT_TGZ_NAME)
        # Make sure that the source dir is deleted
        rm_conandir(self._client_cache.source(conan_reference))
        for dirname, _, filenames in os.walk(dest_folder):
            for fname in filenames:
                touch(os.path.join(dirname, fname))
#       TODO: Download only the CONANFILE file and only download the rest of files
#       in install if needed (not found remote package)
        return files

    def get_recipe_sources(self, conan_reference, dest_folder, remote):
        t1 = time.time()
        zipped_files = self._call_remote(remote, "get_recipe_sources",
                                         conan_reference, dest_folder)
        duration = time.time() - t1
        # log_recipe_download(conan_reference, duration, remote, zipped_files)
        if not zipped_files:
            return

        sources_folder = os.path.join(dest_folder, EXPORT_SOURCES_DIR)
        files = unzip_and_get_files(zipped_files, sources_folder, EXPORT_SOURCES_TGZ_NAME)
        for dirname, _, filenames in os.walk(sources_folder):
            for fname in filenames:
                touch(os.path.join(dirname, fname))

        return files

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
        files = unzip_and_get_files(zipped_files, dest_folder, PACKAGE_TGZ_NAME)
        # Issue #214 https://github.com/conan-io/conan/issues/214
        for dirname, _, filenames in os.walk(dest_folder):
            for fname in filenames:
                touch(os.path.join(dirname, fname))

        return files

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


def compress_conan_files(files, dest_folder, zipped_name, exclude, output):
    if zipped_name not in files:
        output.rewrite_line("Compressing %s..."
                            % ("exported files" if zipped_name == EXPORT_TGZ_NAME else "package"))
        return compress_files(files, zipped_name,
                              excluded=(exclude, CONAN_MANIFEST), dest_dir=dest_folder)
    else:
        the_files = {zipped_name: files[zipped_name],
                     exclude: files[exclude],
                     CONAN_MANIFEST: files[CONAN_MANIFEST]}
        return the_files


def compress_files(files, name, excluded, dest_dir):
    """Compress the package and returns the new dict (name => content) of files,
    only with the conanXX files and the compressed file"""

    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    with open(tgz_path, "wb") as tgz_handle:
        # tgz_contents = BytesIO()
        tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle)

        def addfile(name, abs_path, tar):
            info = tarfile.TarInfo(name=name)
            info.size = os.stat(abs_path).st_size
            info.mode = os.stat(abs_path).st_mode
            if os.path.islink(abs_path):
                info.type = tarfile.SYMTYPE
                info.linkname = os.readlink(abs_path)
                tar.addfile(tarinfo=info)
            else:
                with open(abs_path, 'rb') as file_handler:
                    tar.addfile(tarinfo=info, fileobj=file_handler)

        for filename, abs_path in files.items():
            if filename not in excluded:
                addfile(filename, abs_path, tgz)

        tgz.close()
        ret = {}
        for e in excluded:
            if e in files:
                ret[e] = files[e]

        ret[name] = tgz_path

    return ret


def unzip_and_get_files(files, destination_dir, tgz_name):
    '''Moves all files from package_files, {relative_name: tmp_abs_path}
    to destination_dir, unzipping the "tgz_name" if found'''

    tgz_file = files.pop(tgz_name, None)
    if tgz_file:
        uncompress_file(tgz_file, destination_dir)
        os.remove(tgz_file)

    return relative_dirs(destination_dir)


def uncompress_file(src_path, dest_folder):
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
