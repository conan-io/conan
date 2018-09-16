import os
import time

from conans.client.remote_manager import check_compressed_files
from conans.client.rest.rest_client_common import RestCommonMethods
from conans.client.rest.uploader_downloader import Downloader, Uploader
from conans.errors import NotFoundException, ConanException
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import CONAN_MANIFEST, CONANINFO, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, \
    PACKAGE_TGZ_NAME
from conans.util.files import decode_text
from conans.util.log import logger


class RestV2Methods(RestCommonMethods):

    def __init__(self, remote_url, token, custom_headers, output, requester, verify_ssl,
                 put_headers=None, checksum_deploy=False):

        super(RestV2Methods, self).__init__(remote_url, token, custom_headers, output, requester,
                                            verify_ssl, put_headers)
        self._checksum_deploy = checksum_deploy

    @property
    def remote_api_url(self):
        return "%s/v2" % self.remote_url.rstrip("/")

    def _get_file_list_json(self, url):
        data = self.get_json(url)
        # Discarding (.keys()) still empty metadata for files
        data["files"] = list(data["files"].keys())
        return data

    def _get_remote_file_contents(self, url):
        downloader = Downloader(self.requester, self._output, self.verify_ssl)
        contents = downloader.download(url, auth=self.auth)
        return contents

    def _get_snapshot(self, url, reference):
        try:
            data = self._get_file_list_json(url)
            files_list = [os.path.normpath(filename) for filename in data["files"]]
            reference = data["reference"]
        except NotFoundException:
            files_list = []
        return files_list, reference

    def _get_recipe_snapshot(self, reference):
        url = self._recipe_url(reference)
        snap, reference = self._get_snapshot(url, reference.full_repr())
        reference = ConanFileReference.loads(reference)
        return snap, reference

    def _get_package_snapshot(self, package_reference):
        url = self._package_url(package_reference)
        snap, p_reference = self._get_snapshot(url, package_reference.full_repr())
        reference = PackageReference.loads(p_reference)
        return snap, reference

    def get_conan_manifest(self, conan_reference):
        url = "%s/%s" % (self._recipe_url(conan_reference), CONAN_MANIFEST)
        content = self._get_remote_file_contents(url)
        return FileTreeManifest.loads(decode_text(content))

    def get_package_manifest(self, package_reference):
        url = "%s/%s" % (self._package_url(package_reference), CONAN_MANIFEST)
        content = self._get_remote_file_contents(url)
        return FileTreeManifest.loads(decode_text(content))

    def get_package_info(self, package_reference):
        url = "%s/%s" % (self._package_url(package_reference), CONANINFO)
        content = self._get_remote_file_contents(url)
        return ConanInfo.loads(decode_text(content))

    def get_recipe(self, conan_reference, dest_folder):
        url = self._recipe_url(conan_reference)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(EXPORT_TGZ_NAME, files)
        reference = ConanFileReference.loads(data["reference"])
        if EXPORT_SOURCES_TGZ_NAME in files:
            files.remove(EXPORT_SOURCES_TGZ_NAME)

        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        url = self._recipe_url(reference)
        self._download_and_save_files(url, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret, reference

    def get_recipe_sources(self, conan_reference, dest_folder):
        url = self._recipe_url(conan_reference)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(EXPORT_SOURCES_TGZ_NAME, files)
        if EXPORT_SOURCES_TGZ_NAME not in files:
            return None
        files = [EXPORT_SOURCES_TGZ_NAME, ]

        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        url = self._recipe_url(ConanFileReference.loads(data["reference"]))
        self._download_and_save_files(url, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_package(self, package_reference, dest_folder):
        url = self._package_url(package_reference)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(PACKAGE_TGZ_NAME, files)
        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        url = self._package_url(PackageReference.loads(data["reference"]))
        self._download_and_save_files(url, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_path(self, conan_reference, package_id, path):

        if not package_id:
            url = self._recipe_url(conan_reference)
        else:
            package_ref = PackageReference(conan_reference, package_id)
            url = self._package_url(package_ref)

        try:
            files = self._get_file_list_json(url)
        except NotFoundException:
            if package_id:
                raise NotFoundException("Package %s:%s not found" % (conan_reference, package_id))
            else:
                raise NotFoundException("Recipe %s not found" % str(conan_reference))

        def is_dir(the_path):
            if the_path == ".":
                return True
            for the_file in files["files"]:
                if the_path == the_file:
                    return False
                elif the_file.startswith(the_path):
                    return True
            raise NotFoundException("The specified path doesn't exist")

        if is_dir(path):
            ret = []
            for the_file in files["files"]:
                if path == "." or the_file.startswith(path):
                    tmp = the_file[len(path)-1:].split("/", 1)[0]
                    if tmp not in ret:
                        ret.append(tmp)
            return sorted(ret)
        else:
            url += "/%s" % path
            content = self._get_remote_file_contents(url)
            return decode_text(content)

    def _upload_recipe(self, conan_reference, files_to_upload, retry, retry_wait):
        # Direct upload the recipe
        url = self._recipe_url(conan_reference)
        self._upload_files(files_to_upload, url, retry, retry_wait)

    def _upload_package(self, package_reference, files_to_upload, retry, retry_wait):
        url = self._package_url(package_reference)
        self._upload_files(files_to_upload, url, retry, retry_wait)

    def _upload_files(self, files, base_url, retry, retry_wait):
        t1 = time.time()
        failed = []
        uploader = Uploader(self.requester, self._output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename in sorted(files, reverse=True):
            self._output.rewrite_line("Uploading %s" % filename)
            resource_url = "%s/%s" % (base_url, filename)
            try:
                response = uploader.upload(resource_url, files[filename], auth=self.auth,
                                           dedup=self._checksum_deploy, retry=retry,
                                           retry_wait=retry_wait,
                                           headers=self._put_headers)
                self._output.writeln("")
                if not response.ok:
                    self._output.error("\nError uploading file: %s, '%s'" % (filename,
                                                                             response.content))
                    failed.append(filename)
                else:
                    pass
            except Exception as exc:
                self._output.error("\nError uploading file: %s, '%s'" % (filename, exc))
                failed.append(filename)

        if failed:
            raise ConanException("Execute upload again to retry upload the failed files: %s"
                                 % ", ".join(failed))
        else:
            logger.debug("\nAll uploaded! Total time: %s\n" % str(time.time() - t1))

    def _download_and_save_files(self, base_url, dest_folder, files):
        downloader = Downloader(self.requester, self._output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename in sorted(files, reverse=True):
            if self._output:
                self._output.writeln("Downloading %s" % filename)
            resource_url = "%s/%s" % (base_url, filename)
            abs_path = os.path.join(dest_folder, filename)
            downloader.download(resource_url, abs_path, auth=self.auth)

    def _recipe_url(self, conan_reference):
        url = "%s/conans/%s" % (self.remote_api_url, "/".join(conan_reference))

        if conan_reference.revision:
            url += "#%s" % conan_reference.revision
        return url.replace("#", "%23")

    def _package_url(self, p_reference):
        url = self._recipe_url(p_reference.conan)
        url += "/packages/%s" % p_reference.package_id
        if p_reference.revision:
            url += "#%s" % p_reference.revision
        return url.replace("#", "%23")
