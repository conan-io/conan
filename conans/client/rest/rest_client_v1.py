import os
import time
import traceback
from collections import namedtuple

from six.moves.urllib.parse import parse_qs, urljoin, urlparse, urlsplit

from conans.client.remote_manager import check_compressed_files
from conans.client.rest.client_routes import ClientV1Router
from conans.client.rest.download_cache import CachedFileDownloader
from conans.client.rest.file_uploader import FileUploader
from conans.client.rest.rest_client_common import RestCommonMethods, handle_return_deserializer
from conans.client.rest.file_downloader import FileDownloader
from conans.errors import ConanException, NotFoundException, NoRestV2Available, \
    PackageNotFoundException
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANINFO, CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, \
    PACKAGE_TGZ_NAME
from conans.util.files import decode_text
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
    def router(self):
        return ClientV1Router(self.remote_url.rstrip("/"), self._artifacts_properties,
                              self._matrix_params)

    def _download_files(self, file_urls, snapshot_md5):
        """
        :param: file_urls is a dict with {filename: url}
        :param snapshot_md5: dict with {filaname: md5 checksum} of files to be downloaded

        Its a generator, so it yields elements for memory performance
        """
        downloader = FileDownloader(self.requester, None, self.verify_ssl, self._config)
        download_cache = self._config.download_cache
        if download_cache:
            assert snapshot_md5 is not None, "if download_cache is set, we need the file checksums"
            downloader = CachedFileDownloader(download_cache, downloader)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename, resource_url in sorted(file_urls.items(), reverse=True):
            auth, _ = self._file_server_capabilities(resource_url)
            if download_cache:
                md5 = snapshot_md5[filename]
                contents = downloader.download(resource_url, auth=auth, md5=md5)
            else:
                contents = downloader.download(resource_url, auth=auth)
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

    def get_recipe_manifest(self, ref):
        """Gets a FileTreeManifest from conans"""
        # Obtain the URLs
        url = self.router.recipe_manifest(ref)
        urls = self._get_file_to_url_dict(url)

        md5s = self.get_recipe_snapshot(ref) if self._config.download_cache else None
        # Get the digest
        contents = self._download_files(urls, md5s)
        # Unroll generator and decode shas (plain text)
        contents = {key: decode_text(value) for key, value in dict(contents).items()}
        return FileTreeManifest.loads(contents[CONAN_MANIFEST])

    def get_package_manifest(self, pref):
        """Gets a FileTreeManifest from a package"""
        pref = pref.copy_with_revs(None, None)
        # Obtain the URLs
        url = self.router.package_manifest(pref)
        urls = self._get_file_to_url_dict(url)

        # Get the digest
        md5s = self.get_package_snapshot(pref) if self._config.download_cache else None
        contents = self._download_files(urls, md5s)
        try:
            # Unroll generator and decode shas (plain text)
            content = dict(contents)[CONAN_MANIFEST]
            return FileTreeManifest.loads(decode_text(content))
        except Exception as e:
            msg = "Error retrieving manifest file for package " \
                  "'{}' from remote ({}): '{}'".format(repr(pref), self.remote_url, e)
            logger.error(msg)
            logger.error(traceback.format_exc())
            raise ConanException(msg)

    def get_package_info(self, pref):
        """Gets a ConanInfo file from a package"""
        pref = pref.copy_with_revs(None, None)
        url = self.router.package_download_urls(pref)
        urls = self._get_file_to_url_dict(url)
        if not urls:
            raise PackageNotFoundException(pref)

        if CONANINFO not in urls:
            raise NotFoundException("Package %s doesn't have the %s file!" % (pref,
                                                                              CONANINFO))
        md5s = self.get_package_snapshot(pref) if self._config.download_cache else None
        # Get the info (in memory)
        contents = self._download_files({CONANINFO: urls[CONANINFO]}, md5s)
        # Unroll generator and decode shas (plain text)
        contents = {key: decode_text(value) for key, value in dict(contents).items()}
        return ConanInfo.loads(contents[CONANINFO])

    def _get_file_to_url_dict(self, url, data=None):
        """Call to url and decode the json returning a dict of {filepath: url} dict
        converting the url to a complete url when needed"""
        urls = self.get_json(url, data=data)
        return {filepath: complete_url(self.remote_url, url) for filepath, url in urls.items()}

    def _upload_recipe(self, ref, files_to_upload, retry, retry_wait):
        # Get the upload urls and then upload files
        url = self.router.recipe_upload_urls(ref)
        file_sizes = {filename.replace("\\", "/"): os.stat(abs_path).st_size
                      for filename, abs_path in files_to_upload.items()}
        urls = self._get_file_to_url_dict(url, data=file_sizes)
        if self._matrix_params:
            urls = self.router.add_matrix_params(urls)
        self._upload_files(urls, files_to_upload, self._output, retry, retry_wait,
                           display_name=str(ref))

    def _upload_package(self, pref, files_to_upload, retry, retry_wait):
        # Get the upload urls and then upload files
        url = self.router.package_upload_urls(pref)
        file_sizes = {filename: os.stat(abs_path).st_size for filename,
                      abs_path in files_to_upload.items()}
        logger.debug("Requesting upload urls...")
        urls = self._get_file_to_url_dict(url, data=file_sizes)
        if self._matrix_params:
            urls = self.router.add_matrix_params(urls)
        logger.debug("Requesting upload urls...Done!")
        short_pref_name = "%s:%s" % (pref.ref, pref.id[0:4])
        self._upload_files(urls, files_to_upload, self._output, retry, retry_wait,
                           display_name=short_pref_name)

    def _upload_files(self, file_urls, files, output, retry, retry_wait, display_name=None):
        t1 = time.time()
        failed = []
        uploader = FileUploader(self.requester, output, self.verify_ssl, self._config)
        # conan_package.tgz and conan_export.tgz are uploaded first to avoid uploading conaninfo.txt
        # or conanamanifest.txt with missing files due to a network failure
        for filename, resource_url in sorted(file_urls.items()):
            if output and not output.is_terminal:
                msg = "Uploading: %s" % filename if not display_name else (
                            "Uploading %s -> %s" % (filename, display_name))
                output.writeln(msg)
            auth, dedup = self._file_server_capabilities(resource_url)
            try:
                headers = self._artifacts_properties if not self._matrix_params else {}
                uploader.upload(resource_url, files[filename], auth=auth, dedup=dedup,
                                retry=retry, retry_wait=retry_wait,
                                headers=headers, display_name=display_name)
            except Exception as exc:
                output.error("\nError uploading file: %s, '%s'" % (filename, exc))
                failed.append(filename)

        if failed:
            raise ConanException("Execute upload again to retry upload the failed files: %s"
                                 % ", ".join(failed))
        else:
            logger.debug("UPLOAD: \nAll uploaded! Total time: %s\n" % str(time.time() - t1))

    def _download_files_to_folder(self, file_urls, to_folder, snapshot_md5):
        """
        :param: file_urls is a dict with {filename: abs_path}

        It writes downloaded files to disk (appending to file, only keeps chunks in memory)
        """
        downloader = FileDownloader(self.requester, self._output, self.verify_ssl, self._config)
        download_cache = self._config.download_cache
        if download_cache:
            assert snapshot_md5 is not None, "if download_cache is set, we need the file checksums"
            downloader = CachedFileDownloader(download_cache, downloader)

        ret = {}
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename, resource_url in sorted(file_urls.items(), reverse=True):
            if self._output and not self._output.is_terminal:
                self._output.writeln("Downloading %s" % filename)
            auth, _ = self._file_server_capabilities(resource_url)
            abs_path = os.path.join(to_folder, filename)
            if download_cache:
                md5 = snapshot_md5[filename]
                downloader.download(resource_url, abs_path, auth=auth, md5=md5)
            else:
                downloader.download(resource_url, abs_path, auth=auth)
            ret[filename] = abs_path
        return ret

    def get_recipe(self, ref, dest_folder):
        urls = self._get_recipe_urls(ref)
        urls.pop(EXPORT_SOURCES_TGZ_NAME, None)
        check_compressed_files(EXPORT_TGZ_NAME, urls)
        md5s = self.get_recipe_snapshot(ref) if self._config.download_cache else None
        zipped_files = self._download_files_to_folder(urls, dest_folder, md5s)
        return zipped_files

    def get_recipe_sources(self, ref, dest_folder):
        urls = self._get_recipe_urls(ref)
        check_compressed_files(EXPORT_SOURCES_TGZ_NAME, urls)
        if EXPORT_SOURCES_TGZ_NAME not in urls:
            return None
        urls = {EXPORT_SOURCES_TGZ_NAME: urls[EXPORT_SOURCES_TGZ_NAME]}
        md5s = self.get_recipe_snapshot(ref) if self._config.download_cache else None
        zipped_files = self._download_files_to_folder(urls, dest_folder, md5s)
        return zipped_files

    def _get_recipe_urls(self, ref):
        """Gets a dict of filename:contents from conans"""
        # Get the conanfile snapshot first
        url = self.router.recipe_download_urls(ref)
        urls = self._get_file_to_url_dict(url)
        return urls

    def get_package(self, pref, dest_folder):
        urls = self._get_package_urls(pref)
        check_compressed_files(PACKAGE_TGZ_NAME, urls)
        md5s = self.get_package_snapshot(pref) if self._config.download_cache else None
        zipped_files = self._download_files_to_folder(urls, dest_folder, md5s)
        return zipped_files

    def _get_package_urls(self, pref):
        """Gets a dict of filename:contents from package"""
        url = self.router.package_download_urls(pref)
        urls = self._get_file_to_url_dict(url)
        if not urls:
            raise PackageNotFoundException(pref)

        return urls

    def get_recipe_path(self, ref, path):
        url = self.router.recipe_download_urls(ref)
        return self._get_path(url, path)

    def get_package_path(self, pref, path):
        """Gets a file content or a directory list"""
        url = self.router.package_download_urls(pref)
        return self._get_path(url, path)

    def _get_path(self, url, path):
        urls = self._get_file_to_url_dict(url)

        def is_dir(the_path):
            if the_path == ".":
                return True
            for _the_file in urls:
                if the_path == _the_file:
                    return False
                elif _the_file.startswith(the_path):
                    return True
            raise NotFoundException("The specified path doesn't exist")

        if is_dir(path):
            ret = []
            for the_file in urls:
                if path == "." or the_file.startswith(path):
                    tmp = the_file[len(path) - 1:].split("/", 1)[0]
                    if tmp not in ret:
                        ret.append(tmp)
            return sorted(ret)
        else:
            downloader = FileDownloader(self.requester, None, self.verify_ssl, self._config)
            auth, _ = self._file_server_capabilities(urls[path])
            content = downloader.download(urls[path], auth=auth)

            return decode_text(content)

    def _get_snapshot(self, url):
        try:
            snapshot = self.get_json(url)
            snapshot = {os.path.normpath(filename): the_md5
                        for filename, the_md5 in snapshot.items()}
        except NotFoundException:
            snapshot = []
        return snapshot

    @handle_return_deserializer()
    def _remove_conanfile_files(self, ref, files):
        self.check_credentials()
        payload = {"files": [filename.replace("\\", "/") for filename in files]}
        url = self.router.remove_recipe_files(ref)
        return self._post_json(url, payload)

    @handle_return_deserializer()
    def remove_packages(self, ref, package_ids):
        """ Remove any packages specified by package_ids"""
        self.check_credentials()
        payload = {"package_ids": package_ids}
        url = self.router.remove_packages(ref)
        ret = self._post_json(url, payload)
        if not package_ids and ret.status_code == 404:
            # Double check if it is a 404 because there are no packages
            try:
                if not self.search_packages(ref, query=None):
                    return namedtuple("_", ['status_code', 'content'])(200, b'')
            except Exception as e:
                logger.warning("Unexpected error searching {} packages"
                               " in remote {}: {}".format(ref, self.remote_url, e))
        return ret

    @handle_return_deserializer()
    def remove_conanfile(self, ref):
        """ Remove a recipe and packages """
        self.check_credentials()
        url = self.router.remove_recipe(ref)
        logger.debug("REST: remove: %s" % url)
        response = self.requester.delete(url, auth=self.auth, headers=self.custom_headers,
                                         verify=self.verify_ssl)
        return response

    def get_recipe_revisions(self, ref):
        raise NoRestV2Available("The remote doesn't support revisions")

    def get_package_revisions(self, pref):
        raise NoRestV2Available("The remote doesn't support revisions")

    def get_latest_recipe_revision(self, ref):
        raise NoRestV2Available("The remote doesn't support revisions")

    def get_latest_package_revision(self, pref):
        raise NoRestV2Available("The remote doesn't support revisions")

    def _post_json(self, url, payload):
        logger.debug("REST: post: %s" % url)
        response = self.requester.post(url,
                                       auth=self.auth,
                                       headers=self.custom_headers,
                                       verify=self.verify_ssl,
                                       json=payload)
        return response
