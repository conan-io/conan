import os

import time

from conans.client.rest.differ import diff_snapshots
from conans.client.rest.rest_client_common import RestCommonMethods
from conans.client.rest.uploader_downloader import Downloader, Uploader
from conans.errors import NotFoundException, ConanException
from conans.model import RECIPE_HASH_HEADER, PACKAGE_HASH_HEADER
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.paths import CONAN_MANIFEST, CONANINFO, EXPORT_SOURCES_TGZ_NAME
from conans.util.files import decode_text, sha1sum
from conans.util.log import logger


class RestV2Methods(RestCommonMethods):

    @property
    def remote_api_url(self):
        return "%s/v2" % self.remote_url.rstrip("/")

    def _get_remote_file_contents(self, url):
        downloader = Downloader(self.requester, self._output, self.verify_ssl)
        contents = downloader.download(url, auth=self.auth)
        return contents

    def get_conan_manifest(self, conan_reference):
        url = "%s/conans/%s/%s" % (self.remote_api_url, "/".join(conan_reference), CONAN_MANIFEST)
        content = self._get_remote_file_contents(url)
        return FileTreeManifest.loads(decode_text(content))

    def get_package_manifest(self, package_reference):
        url = "%s/conans/%s/packages/%s/%s" % (self.remote_api_url,
                                               "/".join(package_reference.conan),
                                               package_reference.package_id, CONAN_MANIFEST)
        content = self._get_remote_file_contents(url)
        return FileTreeManifest.loads(decode_text(content))

    def get_package_info(self, package_reference):
        url = "%s/conans/%s/packages/%s/%s" % (self.remote_api_url,
                                               "/".join(package_reference.conan),
                                               package_reference.package_id, CONANINFO)
        content = self._get_remote_file_contents(url)
        return ConanInfo.loads(decode_text(content))

    def get_recipe(self, conan_reference, dest_folder):
        url = "%s/conans/%s" % (self.remote_api_url, "/".join(conan_reference))
        data = self.get_json(url)
        files = data["files"]
        files.pop(EXPORT_SOURCES_TGZ_NAME, None)
        recipe_hash = data["recipe_hash"]
        self._download_and_save_files(url, dest_folder, files, recipe_hash)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_recipe_sources(self, conan_reference, dest_folder):
        url = "%s/conans/%s" % (self.remote_api_url, "/".join(conan_reference))
        data = self.get_json(url)
        files = data["files"]
        if EXPORT_SOURCES_TGZ_NAME not in files:
            return None
        files = {EXPORT_SOURCES_TGZ_NAME: files[EXPORT_SOURCES_TGZ_NAME]}
        recipe_hash = data["recipe_hash"]
        self._download_and_save_files(url, dest_folder, files, recipe_hash)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_package(self, package_reference, dest_folder):
        url = "%s/conans/%s/packages/%s" % (self.remote_api_url, "/".join(package_reference.conan),
                                            package_reference.package_id)
        data = self.get_json(url)
        files = data["files"]
        recipe_hash = data["recipe_hash"]
        package_hash = data["package_hash"]
        self._download_and_save_files(url, dest_folder, files, recipe_hash, package_hash)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_path(self, conan_reference, package_id, path):

        if not package_id:
            url = "%s/conans/%s" % (self.remote_api_url, "/".join(conan_reference))
        else:
            url = "%s/conans/%s/packages/%s" % (self.remote_api_url, "/".join(conan_reference),
                                                package_id)

        try:
            files = self.get_json(url)
        except NotFoundException:
            if package_id:
                raise NotFoundException("Package %s:%s not found" % (conan_reference, package_id))
            else:
                raise NotFoundException("Recipe %s not found" % str(conan_reference))

        def is_dir(the_path):
            if the_path == ".":
                return True
            for the_file in files["files"].keys():
                if the_path == the_file:
                    return False
                elif the_file.startswith(the_path):
                    return True
            raise NotFoundException("The specified path doesn't exist")

        if is_dir(path):
            ret = []
            for the_file in files["files"].keys():
                if path == "." or the_file.startswith(path):
                    tmp = the_file[len(path)-1:].split("/", 1)[0]
                    if tmp not in ret:
                        ret.append(tmp)
            return sorted(ret)
        else:
            if not package_id:
                url = "%s/conans/%s/%s" % (self.remote_api_url, "/".join(conan_reference), path)
            else:
                url = "%s/conans/%s/packages/%s/%s" % (self.remote_api_url, "/".join(conan_reference),
                                                       package_id, path)
            content = self._get_remote_file_contents(url)
            return decode_text(content)

    def upload_recipe(self, conan_reference, the_files, retry, retry_wait, ignore_deleted_file,
                      no_overwrite, recipe_hash):
        self.check_credentials()

        # Get the remote snapshot
        url = "%s/conans/%s" % (self.remote_api_url, "/".join(conan_reference))
        try:
            data = self.get_json(url)
        except NotFoundException:
            data = {"files": {}}

        remote_snapshot = data["files"]
        local_snapshot = {filename: sha1sum(abs_path) for filename, abs_path in the_files.items()}

        # Get the diff
        new, modified, deleted = diff_snapshots(local_snapshot, remote_snapshot)
        if ignore_deleted_file and ignore_deleted_file in deleted:
            deleted.remove(ignore_deleted_file)

        if not new and not deleted and modified in (["conanmanifest.txt"], []):
            return False

        if no_overwrite and remote_snapshot:
            if no_overwrite in ("all", "recipe"):
                raise ConanException("Local recipe is different from the remote recipe. "
                                     "Forbidden overwrite")
        files_to_upload = {filename.replace("\\", "/"): the_files[filename]
                           for filename in new + modified}

        if files_to_upload:
            headers = {RECIPE_HASH_HEADER: recipe_hash}
            self._upload_files(files_to_upload, url, retry, retry_wait, headers)
        if deleted:
            self._remove_conanfile_files(conan_reference, deleted)

        return files_to_upload or deleted

    def upload_package(self, package_reference, the_files, retry, retry_wait, no_overwrite,
                       recipe_hash, package_hash):
        self.check_credentials()

        t1 = time.time()
        # Get the remote snapshot
        url = "%s/conans/%s/packages/%s" % (self.remote_api_url, "/".join(package_reference.conan),
                                            package_reference.package_id)

        try:
            data = self.get_json(url)
        except NotFoundException:
            data = {"files": {}}
        remote_snapshot = data["files"]
        local_snapshot = {filename: sha1sum(abs_path) for filename, abs_path in the_files.items()}

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
            headers = {RECIPE_HASH_HEADER: recipe_hash, PACKAGE_HASH_HEADER: package_hash}
            self._upload_files(files_to_upload, url, retry, retry_wait, headers)
        if deleted:
            self._remove_package_files(package_reference, deleted)

        logger.debug("====> Time rest client upload_package: %f" % (time.time() - t1))
        return files_to_upload or deleted

    def _upload_files(self, files, base_url, retry, retry_wait, headers):
        t1 = time.time()
        failed = []
        uploader = Uploader(self.requester, self._output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename in sorted(files, reverse=True):
            self._output.rewrite_line("Uploading %s" % filename)
            resource_url = "%s/%s" % (base_url, filename)
            try:
                headers.update(self._put_headers)
                response = uploader.upload(resource_url, files[filename], auth=self.auth,
                                           dedup=True, retry=retry, retry_wait=retry_wait,
                                           headers=headers)
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

    def _download_and_save_files(self, base_url, dest_folder, files, recipe_hash, package_hash=None):
        headers = {RECIPE_HASH_HEADER: recipe_hash}
        if package_hash:
            headers[PACKAGE_HASH_HEADER] = package_hash
        downloader = Downloader(self.requester, self._output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename, hash in sorted(files.items(), reverse=True):
            if self._output:
                self._output.writeln("Downloading %s" % filename)
            resource_url = "%s/%s" % (base_url, filename)
            abs_path = os.path.join(dest_folder, filename)
            downloader.download(resource_url, abs_path, auth=self.auth, headers=headers)
