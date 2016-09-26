from conans.errors import ConanException, ConanConnectionError
from requests.exceptions import ConnectionError
from conans.util.files import save, tar_extract, rmdir
from conans.util.log import logger
import traceback
import os
from conans.paths import PACKAGE_TGZ_NAME, CONANINFO, CONAN_MANIFEST, CONANFILE, EXPORT_TGZ_NAME
from io import BytesIO
import tarfile
from conans.util.files import gzopen_without_timestamps
from conans.util.files import touch
import shutil
import time


class RemoteManager(object):
    """ Will handle the remotes to get conans, packages etc """

    def __init__(self, client_cache, remote_client, output):
        self._client_cache = client_cache
        self._output = output
        self._remote_client = remote_client

    def upload_conan(self, conan_reference, remote):
        """Will upload the conans to the first remote"""
        basedir = self._client_cache.export(conan_reference)
        rel_files = self._client_cache.export_paths(conan_reference)
        the_files = {filename: os.path.join(basedir, filename) for filename in rel_files}

        if CONANFILE not in rel_files or CONAN_MANIFEST not in rel_files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(conan_reference))

        # FIXME: Check modified exports by hand?

        if EXPORT_TGZ_NAME not in the_files:
            self._output.rewrite_line("Compressing exported files...")
            the_files = compress_export_files(the_files, basedir)
        else:
            the_files = {EXPORT_TGZ_NAME: the_files[EXPORT_TGZ_NAME],
                         CONANFILE: the_files[CONANFILE],
                         CONAN_MANIFEST: the_files[CONAN_MANIFEST]}
        return self._call_remote(remote, "upload_conan", conan_reference, the_files)

    def upload_package(self, package_reference, remote):
        """Will upload the package to the first remote"""
        t1 = time.time()
        basedir = self._client_cache.package(package_reference)
        rel_files = self._client_cache.package_paths(package_reference)

        self._output.rewrite_line("Checking package integrity...")
        if CONANINFO not in rel_files or CONAN_MANIFEST not in rel_files:
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))

        the_files = {filename: os.path.join(basedir, filename) for filename in rel_files}
        logger.debug("====> Time remote_manager build_files_set : %f" % (time.time() - t1))

        # If package has been modified remove tgz to regenerate it
        read_manifest, expected_manifest = self._client_cache.package_manifests(package_reference)
        if read_manifest is None or read_manifest.file_sums != expected_manifest.file_sums:
            if PACKAGE_TGZ_NAME in the_files:
                del the_files[PACKAGE_TGZ_NAME]
                try:
                    tgz_path = os.path.join(basedir, PACKAGE_TGZ_NAME)
                    os.unlink(tgz_path)
                except Exception:
                    pass
            raise ConanException("Cannot upload corrupted package '%s'" % str(package_reference))
        else:
            self._output.rewrite_line("Package integrity OK!")
        self._output.writeln("")
        logger.debug("====> Time remote_manager check package integrity : %f" % (time.time() - t1))

        # Check if conan_package.tgz is present
        if PACKAGE_TGZ_NAME not in the_files:
            self._output.rewrite_line("Compressing package...")
            the_files = compress_package_files(the_files, basedir)
        else:
            the_files = {PACKAGE_TGZ_NAME: the_files[PACKAGE_TGZ_NAME],
                         CONANINFO: the_files[CONANINFO],
                         CONAN_MANIFEST: the_files[CONAN_MANIFEST]}

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

    def get_conanfile(self, conan_reference, remote):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:content , remote_name)"""
        export_files = self._call_remote(remote, "get_conanfile", conan_reference)
        export_folder = self._client_cache.export(conan_reference)
        uncompress_files(export_files, export_folder, EXPORT_TGZ_NAME)
        # Make sure that the source dir is deleted
        rmdir(self._client_cache.source(conan_reference), True)
#       TODO: Download only the CONANFILE file and only download the rest of files
#       in install if needed (not found remote package)

    def get_package(self, package_reference, remote):
        """
        Read the conans package from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:content , remote_name)"""
        package_files = self._call_remote(remote, "get_package", package_reference)
        destination_dir = self._client_cache.package(package_reference)
        uncompress_files(package_files, destination_dir, PACKAGE_TGZ_NAME)

        # Issue #214 https://github.com/conan-io/conan/issues/214
        for dirname, _, files in os.walk(destination_dir):
            for fname in files:
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
            raise ConanConnectionError("Unable to connect to %s=%s" % (remote.name, remote.url))
        except ConanException:
            raise
        except Exception as exc:
            logger.error(traceback.format_exc())
            raise ConanException(exc)


def compress_package_files(files, pkg_base_path):
    return compress_files(files, PACKAGE_TGZ_NAME, excluded=(CONANINFO, CONAN_MANIFEST), dest_dir=pkg_base_path)


def compress_export_files(files, export_base_path):
    return compress_files(files, EXPORT_TGZ_NAME, excluded=(CONANFILE, CONAN_MANIFEST), dest_dir=export_base_path)


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


def uncompress_files(files, folder, name):
    try:
        for file_name, content in files:
            if os.path.basename(file_name) == name:
                #  Unzip the file and not keep the tgz
                tar_extract(BytesIO(content), folder)
            else:
                save(os.path.join(folder, file_name), content)
    except Exception as e:
        error_msg = "Error while downloading/extracting files to %s\n%s\n" % (folder, str(e))
        # try to remove the files
        try:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                error_msg += "Folder removed"
        except Exception as e:
            error_msg += "Folder not removed, files/package might be damaged, remove manually"
        raise ConanException(error_msg)
