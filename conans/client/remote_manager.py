from conans.errors import ConanException, ConanConnectionError
from requests.exceptions import ConnectionError
from conans.util.files import build_files_set, save, tar_extract, rmdir
from conans.util.log import logger
import traceback
import os
from conans.paths import PACKAGE_TGZ_NAME, CONANINFO, CONAN_MANIFEST, CONANFILE, EXPORT_TGZ_NAME
from io import StringIO, BytesIO
import tarfile
from conans.util.files import gzopen_without_timestamps
from conans.util.files import touch


class RemoteManager(object):
    """ Will handle the remotes to get conans, packages etc """

    def __init__(self, paths, remote_client, output):
        self._paths = paths
        self._output = output
        self._remote_client = remote_client

    def upload_conan(self, conan_reference, remote):
        """Will upload the conans to the first remote"""
        basedir = self._paths.export(conan_reference)
        rel_files = self._paths.export_paths(conan_reference)

        the_files = build_files_set(basedir, rel_files)
        the_files = compress_export_files(the_files)
        return self._call_remote(remote, "upload_conan", conan_reference, the_files)

    def upload_package(self, package_reference, remote):
        """Will upload the package to the first remote"""
        basedir = self._paths.package(package_reference)
        rel_files = self._paths.package_paths(package_reference)

        the_files = build_files_set(basedir, rel_files)
        self._output.rewrite_line("Compressing package...")
        the_files = compress_package_files(the_files)
        return self._call_remote(remote, "upload_package", package_reference, the_files)

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
        export_folder = self._paths.export(conan_reference)
        uncompress_files(export_files, export_folder, EXPORT_TGZ_NAME)
        # Make sure that the source dir is deleted
        rmdir(self._paths.source(conan_reference))
#       TODO: Download only the CONANFILE file and only download the rest of files
#       in install if needed (not found remote package)

    def get_package(self, package_reference, remote):
        """
        Read the conans package from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:content , remote_name)"""
        package_files = self._call_remote(remote, "get_package", package_reference)
        destination_dir = self._paths.package(package_reference)
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


def compress_package_files(files):
    return compress_files(files, PACKAGE_TGZ_NAME, excluded=(CONANINFO, CONAN_MANIFEST))


def compress_export_files(files):
    return compress_files(files, EXPORT_TGZ_NAME, excluded=(CONANFILE, CONAN_MANIFEST))


def compress_files(files, name, excluded):
    """Compress the package and returns the new dict (name => content) of files,
    only with the conanXX files and the compressed file"""

    tgz_contents = BytesIO()
    tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_contents)

    def addfile(name, file_info, tar):
        info = tarfile.TarInfo(name=name)
        the_str = BytesIO(file_info["contents"])
        info.size = len(file_info["contents"])
        info.mode = file_info["mode"]
        tar.addfile(tarinfo=info, fileobj=the_str)

    for the_file, info in files.items():
        if the_file not in excluded:
            addfile(the_file, info, tgz)

    tgz.close()
    ret = {}
    for e in excluded:
        if e in files:
            ret[e] = files[e]["contents"]
    ret[name] = tgz_contents.getvalue()

    return ret


def uncompress_files(files, folder, name):
    for file_name, content in files:
        if os.path.basename(file_name) != name:
            save(os.path.join(folder, file_name), content)
        else:
            #  Unzip the file
            tar_extract(BytesIO(content), folder)
