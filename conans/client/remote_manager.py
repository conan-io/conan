from conans.errors import ConanException, NotFoundException, ConanConnectionError
from requests.exceptions import ConnectionError
from conans.util.files import build_files_set, save, tar_extract
from conans.util.log import logger
import traceback
from conans.errors import ConanOutdatedClient
import os
from conans.paths import PACKAGE_TGZ_NAME, CONANINFO, CONAN_MANIFEST, CONANFILE, EXPORT_TGZ_NAME
from cStringIO import StringIO
import tarfile
from conans.util.files import gzopen_without_timestamps


class RemoteManager(object):
    """ Will handle the remotes to get conans, packages etc """

    def __init__(self, paths, remotes, remote_client, output):
        """
        remotes is a list of tuples of remotename: url EX: [('default', 'http://www.conans.com')]
        client_factory: Factory for generate remote clients, can be replaced if needed for
                        testing purpose or handle different adapter than rest.

        """
        self._paths = paths
        self._output = output
        self._remotes = remotes
        self._remote_client = remote_client

    @property
    def remote_names(self):
        """ return: list of remote names as strings
        """
        return [remote[0] for remote in self._remotes]

    def remote_url(self, remotename):
        """ return: the url as string of a given remote by name
        raise ConanException if not found
        """
        for remote in self._remotes:
            if remote[0] == remotename:
                return remote[1]
        raise ConanException("Remote %s not found" % remotename)

    def upload_conan(self, conan_reference, remote=None):
        """Will upload the conans to the first remote"""

        # Old channel files...
        basedir = self._paths.export(conan_reference)
        rel_files = self._paths.export_paths(conan_reference)

        the_files = build_files_set(basedir, rel_files)
        the_files = compress_export_files(the_files)
        return self._call_without_remote_selection(remote,
                                                   "upload_conan", conan_reference, the_files)

    def upload_package(self, package_reference, remote=None):
        """Will upload the package to the first remote"""
        basedir = self._paths.package(package_reference)
        rel_files = self._paths.package_paths(package_reference)

        the_files = build_files_set(basedir, rel_files)
        self._output.rewrite_line("Compressing package...")
        the_files = compress_package_files(the_files)
        return self._call_without_remote_selection(remote, "upload_package",
                                                   package_reference, the_files)

    def get_conan_digest(self, conan_reference, remote=None):
        """
        Read ConanDigest from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (ConanDigest, remote_name)"""
        return self._call_with_remote_selection(remote, "get_conan_digest", conan_reference)

    def get_conanfile(self, conan_reference, remote=None):
        """
        Read the conans from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:content , remote_name)"""
        export_files = self._call_with_remote_selection(remote, "get_conanfile", conan_reference)
        export_folder = self._paths.export(conan_reference)
        uncompress_files(export_files, export_folder, EXPORT_TGZ_NAME)
#       TODO: Download only the CONANFILE file and only download the rest of files
#       in install if needed (not found remote package)

    def get_package(self, package_reference, remote=None):
        """
        Read the conans package from remotes
        Will iterate the remotes to find the conans unless remote was specified

        returns (dict relative_filepath:content , remote_name)"""
        package_files = self._call_with_remote_selection(remote, "get_package", package_reference)
        uncompress_files(package_files, self._paths.package(package_reference), PACKAGE_TGZ_NAME)

    def search(self, pattern=None, remote=None, ignorecase=True):
        """
        Search exported conans information from remotes

        returns (dict str(conan_ref): {packages_info}"""
        return self._call_without_remote_selection(remote, "search", pattern, ignorecase)

    def remove(self, conan_ref, remote):
        """
        Removed conans or packages from remote
        """
        return self._call_with_remote_selection(remote, "remove", conan_ref)

    def remove_packages(self, conan_ref, remove_ids, remote):
        """
        Removed conans or packages from remote
        """
        return self._call_with_remote_selection(remote, "remove_packages", conan_ref, remove_ids)

    @property
    def default_remote(self):
        try:
            return self.remote_names[0]
        except IndexError:
            raise ConanException("There is no configured default remote")

    def authenticate(self, remote, name, password):
        return self._call_without_remote_selection(remote, 'authenticate', name, password)

    def _call_without_remote_selection(self, remote, method, *argc, **argv):

        if not remote:
            remote = self.default_remote

        self._remote_client.remote_url = self.remote_url(remote)
        try:
            return getattr(self._remote_client, method)(*argc, **argv)
        except ConnectionError as exc:
            raise ConanConnectionError("Unable to connect to %s=%s"
                                       % (remote, self._remote_client.remote_url))
        except ConanException:
            raise
        except Exception as exc:
            logger.error(traceback.format_exc())
            raise ConanException(exc)

    def _call_with_remote_selection(self, remote, method, *argc, **argv):
        """
        Iterates in remotes until a response is found
        """
        if remote:
            return self._call_without_remote_selection(remote, method, *argc, **argv)

        for remote in self.remote_names:
            logger.debug("Trying with remote %s" % self.remote_url(remote))
            self._remote_client.remote_url = self.remote_url(remote)
            try:
                result = self._call_without_remote_selection(remote, method, *argc, **argv)
                self._output.success("Found in remote '%s'" % remote)
                return result
            # If exception continue with the next
            except (ConanOutdatedClient, ConanConnectionError) as exc:
                self._output.warn(str(exc))
                if remote == self._remotes[-1][0]:  # Last element not found
                    raise ConanConnectionError("All remotes failed")
            except NotFoundException as exc:
                if remote == self._remotes[-1][0]:  # Last element not found
                    logger.debug("Not found in any remote, raising...%s" % exc)
                    raise

        raise ConanException("No remote defined")


def compress_package_files(files):
    return compress_files(files, PACKAGE_TGZ_NAME, excluded=(CONANINFO, CONAN_MANIFEST))


def compress_export_files(files):
    return compress_files(files, EXPORT_TGZ_NAME, excluded=(CONANFILE, CONAN_MANIFEST))


def compress_files(files, name, excluded):
    """Compress the package and returns the new dict (name => content) of files,
    only with the conanXX files and the compressed file"""

    tgz_contents = StringIO()
    tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_contents)

    def addfile(name, contents, tar):
        info = tarfile.TarInfo(name=name)
        string = StringIO(contents)
        info.size = len(contents)
        tar.addfile(tarinfo=info, fileobj=string)

    for the_file, content in files.iteritems():
        if the_file not in excluded:
            addfile(the_file, content, tgz)

    tgz.close()
    ret = {}
    for e in excluded:
        if e in files:
            ret[e] = files[e]
    ret[name] = tgz_contents.getvalue()

    return ret


def uncompress_files(files, folder, name):
    for file_name, content in files:
        if os.path.basename(file_name) != name:
            save(os.path.join(folder, file_name), content)
        else:
            #  Unzip the file
            tar_extract(StringIO(content), folder)
