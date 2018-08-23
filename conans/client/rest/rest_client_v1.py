import os
import time

from six.moves.urllib.parse import urlparse, urljoin, urlsplit, parse_qs

from conans.client.remote_manager import check_compressed_files
from conans.client.rest.differ import diff_snapshots
from conans.client.rest.rest_client_common import RestCommonMethods
from conans.client.rest.uploader_downloader import Downloader, Uploader
from conans.errors import NotFoundException, ConanException
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.paths import CONAN_MANIFEST, CONANINFO, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, \
    PACKAGE_TGZ_NAME
from conans.util.files import decode_text, md5sum
from conans.util.log import logger


def complete_url(base_url, url):
    """ Ensures that an url is absolute by completing relative urls with
        the remote url. urls that are already absolute are not modified.
    """
    if bool(urlparse(url).netloc):
        return url
    return urljoin(base_url, url)


class RestV1Methods(RestCommonMethods):

    @property
    def remote_api_url(self):
        return "%s/v1" % self.remote_url.rstrip("/")

    def _download_files(self, file_urls, output=None):
        """
        :param: file_urls is a dict with {filename: url}

        Its a generator, so it yields elements for memory performance
        """
        downloader = Downloader(self.requester, output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename, resource_url in sorted(file_urls.items(), reverse=True):
            if output:
                output.writeln("Downloading %s" % filename)
            auth, _ = self._file_server_capabilities(resource_url)
            contents = downloader.download(resource_url, auth=auth)
            if output:
                output.writeln("")
            yield os.path.normpath(filename), contents

    def _file_server_capabilities(self, resource_url):
        auth = None
        dedup = False
        urltokens = urlsplit(resource_url)
        query_string = urltokens[3]
        parsed_string_dict = parse_qs(query_string)
        if "signature" not in parsed_string_dict and "Signature" not in parsed_string_dict:
            # If monolithic server, we can use same auth, and server understand dedup
            auth = self.auth
            dedup = True
        return auth, dedup

    def get_conan_manifest(self, conan_reference):
        """Gets a FileTreeManifest from conans"""

        # Obtain the URLs
        url = "%s/conans/%s/digest" % (self.remote_api_url, "/".join(conan_reference))
        urls = self._get_file_to_url_dict(url)

        # Get the digest
        contents = self._download_files(urls)
        # Unroll generator and decode shas (plain text)
        contents = {key: decode_text(value) for key, value in dict(contents).items()}
        return FileTreeManifest.loads(contents[CONAN_MANIFEST])

    def get_package_manifest(self, package_reference):
        """Gets a FileTreeManifest from a package"""

        # Obtain the URLs
        url = "%s/conans/%s/packages/%s/digest" % (self.remote_api_url,
                                                   "/".join(package_reference.conan),
                                                   package_reference.package_id)
        urls = self._get_file_to_url_dict(url)

        # Get the digest
        contents = self._download_files(urls)
        # Unroll generator and decode shas (plain text)
        contents = {key: decode_text(value) for key, value in dict(contents).items()}
        return FileTreeManifest.loads(contents[CONAN_MANIFEST])

    def get_package_info(self, package_reference):
        """Gets a ConanInfo file from a package"""

        url = "%s/conans/%s/packages/%s/download_urls" % (self.remote_api_url,
                                                          "/".join(package_reference.conan),
                                                          package_reference.package_id)
        urls = self._get_file_to_url_dict(url)
        if not urls:
            raise NotFoundException("Package not found!")

        if CONANINFO not in urls:
            raise NotFoundException("Package %s doesn't have the %s file!" % (package_reference,
                                                                              CONANINFO))
        # Get the info (in memory)
        contents = self._download_files({CONANINFO: urls[CONANINFO]})
        # Unroll generator and decode shas (plain text)
        contents = {key: decode_text(value) for key, value in dict(contents).items()}
        return ConanInfo.loads(contents[CONANINFO])

    def _get_file_to_url_dict(self, url, data=None):
        """Call to url and decode the json returning a dict of {filepath: url} dict
        converting the url to a complete url when needed"""
        urls = self.get_json(url, data=data)
        return {filepath: complete_url(self.remote_url, url) for filepath, url in urls.items()}

    def _upload_files(self, file_urls, files, output, retry, retry_wait):
        t1 = time.time()
        failed = []
        uploader = Uploader(self.requester, output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename, resource_url in sorted(file_urls.items(), reverse=True):
            output.rewrite_line("Uploading %s" % filename)
            auth, dedup = self._file_server_capabilities(resource_url)
            try:
                response = uploader.upload(resource_url, files[filename], auth=auth, dedup=dedup,
                                           retry=retry, retry_wait=retry_wait, headers=self._put_headers)
                output.writeln("")
                if not response.ok:
                    output.error("\nError uploading file: %s, '%s'" % (filename, response.content))
                    failed.append(filename)
                else:
                    pass
            except Exception as exc:
                output.error("\nError uploading file: %s, '%s'" % (filename, exc))
                failed.append(filename)

        if failed:
            raise ConanException("Execute upload again to retry upload the failed files: %s"
                                 % ", ".join(failed))
        else:
            logger.debug("\nAll uploaded! Total time: %s\n" % str(time.time() - t1))

    def _download_files_to_folder(self, file_urls, to_folder):
        """
        :param: file_urls is a dict with {filename: abs_path}

        It writes downloaded files to disk (appending to file, only keeps chunks in memory)
        """
        downloader = Downloader(self.requester, self._output, self.verify_ssl)
        ret = {}
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename, resource_url in sorted(file_urls.items(), reverse=True):
            if self._output:
                self._output.writeln("Downloading %s" % filename)
            auth, _ = self._file_server_capabilities(resource_url)
            abs_path = os.path.join(to_folder, filename)
            downloader.download(resource_url, abs_path, auth=auth)
            if self._output:
                self._output.writeln("")
            ret[filename] = abs_path
        return ret

    def get_recipe(self, conan_reference, dest_folder):
        urls = self._get_recipe_urls(conan_reference)
        urls.pop(EXPORT_SOURCES_TGZ_NAME, None)
        check_compressed_files(EXPORT_TGZ_NAME, urls)
        zipped_files = self._download_files_to_folder(urls, dest_folder)
        return zipped_files, conan_reference

    def get_recipe_sources(self, conan_reference, dest_folder):
        urls = self._get_recipe_urls(conan_reference)
        check_compressed_files(EXPORT_SOURCES_TGZ_NAME, urls)
        if EXPORT_SOURCES_TGZ_NAME not in urls:
            return None
        urls = {EXPORT_SOURCES_TGZ_NAME: urls[EXPORT_SOURCES_TGZ_NAME]}
        zipped_files = self._download_files_to_folder(urls, dest_folder)
        return zipped_files

    def _get_recipe_urls(self, conan_reference):
        """Gets a dict of filename:contents from conans"""
        # Get the conanfile snapshot first
        url = "%s/conans/%s/download_urls" % (self.remote_api_url, "/".join(conan_reference))
        urls = self._get_file_to_url_dict(url)
        return urls

    def get_package(self, package_reference, dest_folder):
        urls = self._get_package_urls(package_reference)
        check_compressed_files(PACKAGE_TGZ_NAME, urls)
        zipped_files = self._download_files_to_folder(urls, dest_folder)
        return zipped_files

    def _get_package_urls(self, package_reference):
        """Gets a dict of filename:contents from package"""
        url = "%s/conans/%s/packages/%s/download_urls" % (self.remote_api_url,
                                                          "/".join(package_reference.conan),
                                                          package_reference.package_id)
        urls = self._get_file_to_url_dict(url)
        if not urls:
            raise NotFoundException("Package not found!")

        return urls

    def upload_recipe(self, conan_reference, the_files, retry, retry_wait, ignore_deleted_file,
                      no_overwrite):
        """
        the_files: dict with relative_path: content
        """
        self.check_credentials()

        # Get the remote snapshot
        remote_snapshot = self._get_conan_snapshot(conan_reference)
        local_snapshot = {filename: md5sum(abs_path) for filename, abs_path in the_files.items()}

        # Get the diff
        new, modified, deleted = diff_snapshots(local_snapshot, remote_snapshot)
        if ignore_deleted_file and ignore_deleted_file in deleted:
            deleted.remove(ignore_deleted_file)

        if not new and not deleted and modified in (["conanmanifest.txt"], []):
            return False, conan_reference

        if no_overwrite and remote_snapshot:
            if no_overwrite in ("all", "recipe"):
                raise ConanException("Local recipe is different from the remote recipe. "
                                     "Forbidden overwrite")
        files_to_upload = {filename.replace("\\", "/"): the_files[filename]
                           for filename in new + modified}

        if files_to_upload:
            # Get the upload urls
            url = "%s/conans/%s/upload_urls" % (self.remote_api_url, "/".join(conan_reference))
            filesizes = {filename.replace("\\", "/"): os.stat(abs_path).st_size
                         for filename, abs_path in files_to_upload.items()}
            urls = self._get_file_to_url_dict(url, data=filesizes)
            self._upload_files(urls, files_to_upload, self._output, retry, retry_wait)
        if deleted:
            self._remove_conanfile_files(conan_reference, deleted)

        return (files_to_upload or deleted), conan_reference

    def upload_package(self, package_reference, the_files, retry, retry_wait, no_overwrite):
        """
        basedir: Base directory with the files to upload (for read the files in disk)
        relative_files: relative paths to upload
        """
        self.check_credentials()

        t1 = time.time()
        # Get the remote snapshot
        remote_snapshot = self._get_package_snapshot(package_reference)
        local_snapshot = {filename: md5sum(abs_path) for filename, abs_path in the_files.items()}

        # Get the diff
        new, modified, deleted = diff_snapshots(local_snapshot, remote_snapshot)
        if not new and not deleted and modified in (["conanmanifest.txt"], []):
            return False

        if no_overwrite and remote_snapshot:
            if no_overwrite == "all":
                raise ConanException("Local package is different from the remote package. "
                                     "Forbidden overwrite")

        files_to_upload = {filename: the_files[filename] for filename in new + modified}
        if files_to_upload:        # Obtain upload urls
            url = "%s/conans/%s/packages/%s/upload_urls" % (self.remote_api_url,
                                                            "/".join(package_reference.conan),
                                                            package_reference.package_id)
            filesizes = {filename: os.stat(abs_path).st_size for filename,
                         abs_path in files_to_upload.items()}
            self._output.rewrite_line("Requesting upload permissions...")
            urls = self._get_file_to_url_dict(url, data=filesizes)
            self._output.rewrite_line("Requesting upload permissions...Done!")
            self._output.writeln("")
            self._upload_files(urls, files_to_upload, self._output, retry, retry_wait)
        if deleted:
            raise Exception("This shouldn't be happening, deleted files "
                            "in local package present in remote: %s.\n Please, report it at "
                            "https://github.com/conan-io/conan/issues " % str(deleted))

        logger.debug("====> Time rest client upload_package: %f" % (time.time() - t1))
        return files_to_upload or deleted

    def _get_conan_snapshot(self, reference):
        url = "%s/conans/%s" % (self.remote_api_url, '/'.join(reference))
        try:
            snapshot = self.get_json(url)
        except NotFoundException:
            snapshot = {}
        norm_snapshot = {os.path.normpath(filename): the_md5
                         for filename, the_md5 in snapshot.items()}
        return norm_snapshot

    def _get_package_snapshot(self, package_reference):
        url = "%s/conans/%s/packages/%s" % (self.remote_api_url,
                                            "/".join(package_reference.conan),
                                            package_reference.package_id)
        try:
            snapshot = self.get_json(url)
        except NotFoundException:
            snapshot = {}
        norm_snapshot = {os.path.normpath(filename): the_md5
                         for filename, the_md5 in snapshot.items()}
        return norm_snapshot

    def get_path(self, conan_reference, package_id, path):
        """Gets a file content or a directory list"""

        if not package_id:
            url = "%s/conans/%s/download_urls" % (self.remote_api_url, "/".join(conan_reference))
        else:
            url = "%s/conans/%s/packages/%s/download_urls" % (self.remote_api_url,
                                                              "/".join(conan_reference),
                                                              package_id)
        try:
            urls = self._get_file_to_url_dict(url)
        except NotFoundException:
            if package_id:
                raise NotFoundException("Package %s:%s not found" % (conan_reference, package_id))
            else:
                raise NotFoundException("Recipe %s not found" % str(conan_reference))

        def is_dir(the_path):
            if the_path == ".":
                return True

            for the_file in urls:
                if the_path == the_file:
                    return False
                elif the_file.startswith(the_path):
                    return True
            raise NotFoundException("The specified path doesn't exist")

        if is_dir(path):
            ret = []
            for the_file in urls:
                if path == "." or the_file.startswith(path):
                    tmp = the_file[len(path)-1:].split("/", 1)[0]
                    if tmp not in ret:
                        ret.append(tmp)
            return sorted(ret)
        else:
            downloader = Downloader(self.requester, None, self.verify_ssl)
            auth, _ = self._file_server_capabilities(urls[path])
            content = downloader.download(urls[path], auth=auth)

            return decode_text(content)
