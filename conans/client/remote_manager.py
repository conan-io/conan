import os
import shutil
import tarfile
import time
import traceback

from requests.exceptions import ConnectionError

from conans.errors import ConanException, ConanConnectionError
from conans.util.files import tar_extract, relative_dirs, rmdir
from conans.util.log import logger
from conans.paths import PACKAGE_TGZ_NAME, CONANINFO, CONAN_MANIFEST, CONANFILE, EXPORT_TGZ_NAME,\
    rm_conandir
from conans.util.files import gzopen_without_timestamps
from conans.util.files import touch


class RemoteManager(object):
    """ Will handle the remotes to get conans, packages etc """

    def __init__(self, client_cache, remote_client, output):
        self._client_cache = client_cache
        self._output = output
        self._remote_client = remote_client

    def upload_conan(self, conan_reference, remote):
        """Will upload the conans to the first remote"""
        export_folder = self._client_cache.export(conan_reference)
        rel_files = relative_dirs(export_folder)
        the_files = {filename: os.path.join(export_folder, filename) for filename in rel_files}

        if CONANFILE not in rel_files or CONAN_MANIFEST not in rel_files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(conan_reference))

        # FIXME: Check modified exports by hand?
        the_files = compress_conan_files(the_files, export_folder, EXPORT_TGZ_NAME,
                                         CONANFILE, self._output)

        return self._call_remote(remote, "upload_conan", conan_reference, the_files)

    def upload_package(self, package_reference, remote):
        """Will upload the package to the first remote"""
        t1 = time.time()
        # existing package, will use short paths if defined
        package_folder = self._client_cache.package(package_reference, short_paths=None)
        # Get all the files in that directory
        rel_files = relative_dirs(package_folder)

        self._output.rewrite_line("Checking package integrity...")
        if CONANINFO not in rel_files or CONAN_MANIFEST not in rel_files:
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))

        the_files = {filename: os.path.join(package_folder, filename) for filename in rel_files}
        logger.debug("====> Time remote_manager build_files_set : %f" % (time.time() - t1))

        # If package has been modified remove tgz to regenerate it
        read_manifest, expected_manifest = self._client_cache.package_manifests(package_reference)

        # Deals with the problem of generated .pyc, which is an issue for python packages
        # TODO: refactor and improve the reading files + Manifests prior to upload for both
        # recipes and packages
        diff = set(expected_manifest.file_sums.keys()).difference(read_manifest.file_sums.keys())
        for d in diff:
            if d.endswith(".pyc"):
                del expected_manifest.file_sums[d]
                # It has to be in files, otherwise couldn't be in expected_manifest
                del the_files[d]

        if read_manifest is None or read_manifest.file_sums != expected_manifest.file_sums:
            if PACKAGE_TGZ_NAME in the_files:
                try:
                    tgz_path = os.path.join(package_folder, PACKAGE_TGZ_NAME)
                    os.unlink(tgz_path)
                except Exception:
                    pass
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))
        else:
            self._output.rewrite_line("Package integrity OK!")
        self._output.writeln("")
        logger.debug("====> Time remote_manager check package integrity : %f" % (time.time() - t1))

        the_files = compress_conan_files(the_files, package_folder, PACKAGE_TGZ_NAME,
                                         CONANINFO, self._output)

        tmp = self._call_remote(remote, "upload_package", package_reference, the_files)
        logger.debug("====> Time remote_manager upload_package: %f" % (time.time() - t1))
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

    def get_recipe(self, conan_reference, dest_folder, remote):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""
        rmdir(dest_folder)  # Remove first the destination folder
        zipped_files = self._call_remote(remote, "get_recipe", conan_reference, dest_folder)
        files = unzip_and_get_files(zipped_files, dest_folder, EXPORT_TGZ_NAME)
        # Make sure that the source dir is deleted
        rm_conandir(self._client_cache.source(conan_reference))
        for dirname, _, filenames in os.walk(dest_folder):
            for fname in filenames:
                touch(os.path.join(dirname, fname))
#       TODO: Download only the CONANFILE file and only download the rest of files
#       in install if needed (not found remote package)
        return files

    def get_package(self, package_reference, dest_folder, remote):
        """
        Read the conans package from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:abs_path , remote_name)"""
        rm_conandir(dest_folder)  # Remove first the destination folder
        zipped_files = self._call_remote(remote, "get_package", package_reference, dest_folder)
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
        except ConanException:
            raise
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
