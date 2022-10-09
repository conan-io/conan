import copy
import os
import time

from conan.api.output import ConanOutput

from conans.client.downloaders.caching_file_downloader import CachingFileDownloader
from conans.client.remote_manager import check_compressed_files
from conans.client.rest.client_routes import ClientV2Router
from conans.client.rest.file_uploader import FileUploader
from conans.client.rest.rest_client_common import RestCommonMethods, get_exception_from_error
from conans.errors import ConanException, NotFoundException, PackageNotFoundException, \
    RecipeNotFoundException, AuthenticationException, ForbiddenException
from conans.model.package_ref import PkgReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.util.dates import from_iso8601_to_timestamp


class RestV2Methods(RestCommonMethods):

    def __init__(self, remote_url, token, custom_headers, requester, config, verify_ssl,
                 checksum_deploy=False):

        super(RestV2Methods, self).__init__(remote_url, token, custom_headers, requester,
                                            config, verify_ssl)
        self._checksum_deploy = checksum_deploy

    @property
    def router(self):
        return ClientV2Router(self.remote_url.rstrip("/"))

    def _get_file_list_json(self, url):
        data = self.get_json(url)
        # Discarding (.keys()) still empty metadata for files
        data["files"] = list(data["files"].keys())
        return data

    def _get_snapshot(self, url):
        try:
            data = self._get_file_list_json(url)
            files_list = [os.path.normpath(filename) for filename in data["files"]]
        except NotFoundException:
            files_list = []
        return files_list

    def get_recipe(self, ref, dest_folder):
        url = self.router.recipe_snapshot(ref)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(EXPORT_TGZ_NAME, files)
        if EXPORT_SOURCES_TGZ_NAME in files:
            files.remove(EXPORT_SOURCES_TGZ_NAME)

        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        urls = {fn: self.router.recipe_file(ref, fn) for fn in files}
        self._download_and_save_files(urls, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_recipe_sources(self, ref, dest_folder):
        # If revision not specified, check latest
        if not ref.revision:
            ref, _ = self.get_latest_recipe_reference(ref)
        url = self.router.recipe_snapshot(ref)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(EXPORT_SOURCES_TGZ_NAME, files)
        if EXPORT_SOURCES_TGZ_NAME not in files:
            return None
        files = [EXPORT_SOURCES_TGZ_NAME, ]

        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        urls = {fn: self.router.recipe_file(ref, fn) for fn in files}
        self._download_and_save_files(urls, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_package(self, pref, dest_folder):
        url = self.router.package_snapshot(pref)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(PACKAGE_TGZ_NAME, files)
        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        urls = {fn: self.router.package_file(pref, fn) for fn in files}
        self._download_and_save_files(urls, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    @staticmethod
    def _is_dir(path, files):
        if path == ".":
            return True
        for the_file in files["files"]:
            if path == the_file:
                return False
            elif the_file.startswith(path):
                return True
        raise NotFoundException("The specified path doesn't exist")

    @staticmethod
    def _list_dir_contents(path, files):
        ret = []
        for the_file in files["files"]:
            if path == "." or the_file.startswith(path):
                tmp = the_file[len(path) - 1:].split("/", 1)[0]
                if tmp not in ret:
                    ret.append(tmp)
        return sorted(ret)

    def _upload_recipe(self, ref, files_to_upload):
        # Direct upload the recipe
        urls = {fn: self.router.recipe_file(ref, fn)
                for fn in files_to_upload}
        self._upload_files(files_to_upload, urls)

    def _upload_package(self, pref, files_to_upload):
        urls = {fn: self.router.package_file(pref, fn)
                for fn in files_to_upload}
        self._upload_files(files_to_upload, urls)

    def _upload_files(self, files, urls):
        t1 = time.time()
        failed = []
        uploader = FileUploader(self.requester, self.verify_ssl, self._config)
        # conan_package.tgz and conan_export.tgz are uploaded first to avoid uploading conaninfo.txt
        # or conanamanifest.txt with missing files due to a network failure
        output = ConanOutput()
        for filename in sorted(files):
            if output and not output.is_terminal:
                msg ="-> %s" % filename
                output.info(msg)
            resource_url = urls[filename]
            try:
                headers = {}
                uploader.upload(resource_url, files[filename], auth=self.auth,
                                dedup=self._checksum_deploy,
                                headers=headers)
            except (AuthenticationException, ForbiddenException):
                raise
            except Exception as exc:
                output.error("\nError uploading file: %s, '%s'" % (filename, exc))
                failed.append(filename)

        if failed:
            raise ConanException("Execute upload again to retry upload the failed files: %s"
                                 % ", ".join(failed))

    def _download_and_save_files(self, urls, dest_folder, files):
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        retry = self._config.get("core.download:retry", check_type=int, default=2)
        retry_wait = self._config.get("core.download:retry_wait", check_type=int, default=0)
        download_cache = self._config.get("core.download:download_cache")
        if download_cache and not os.path.isabs(download_cache):
            raise ConanException("core.download:download_cache must be an absolute path")
        downloader = CachingFileDownloader(self.requester, download_cache=download_cache)
        for filename in sorted(files, reverse=True):
            resource_url = urls[filename]
            abs_path = os.path.join(dest_folder, filename)
            downloader.download(url=resource_url, file_path=abs_path, auth=self.auth,
                                verify_ssl=self.verify_ssl, retry=retry, retry_wait=retry_wait)

    def _remove_recipe_files(self, ref, files):
        # V2 === revisions, do not remove files, it will create a new revision if the files changed
        return

    def remove_all_packages(self, ref):
        """ Remove all packages from the specified reference"""
        self.check_credentials()
        assert ref.revision is not None, "remove_packages needs RREV"

        url = self.router.remove_all_packages(ref)
        response = self.requester.delete(url, auth=self.auth, verify=self.verify_ssl,
                                         headers=self.custom_headers)
        if response.status_code == 404:
            # Double check if it is a 404 because there are no packages
            try:
                package_search_url = self.router.search_packages(ref)
                if not self.get_json(package_search_url):
                    return
            except Exception as e:
                pass
        if response.status_code != 200:  # Error message is text
            # To be able to access ret.text (ret.content are bytes)
            response.charset = "utf-8"
            raise get_exception_from_error(response.status_code)(response.text)

    def remove_packages(self, prefs):
        self.check_credentials()
        for pref in prefs:
            if not pref.revision:
                prevs = self.get_package_revisions_references(pref)
            else:
                prevs = [pref]
            for prev in prevs:
                url = self.router.remove_package(prev)
                response = self.requester.delete(url, auth=self.auth, headers=self.custom_headers,
                                                 verify=self.verify_ssl)
                if response.status_code == 404:
                    raise PackageNotFoundException(pref)
                if response.status_code != 200:  # Error message is text
                    # To be able to access ret.text (ret.content are bytes)
                    response.charset = "utf-8"
                    raise get_exception_from_error(response.status_code)(response.text)

    def remove_recipe(self, ref):
        """ Remove a recipe and packages """
        self.check_credentials()
        if ref.revision is None:
            # Remove all the RREVs
            refs = self.get_recipe_revisions_references(ref)
        else:
            refs = [ref]

        for ref in refs:
            url = self.router.remove_recipe(ref)
            response = self.requester.delete(url, auth=self.auth, headers=self.custom_headers,
                                             verify=self.verify_ssl)
            if response.status_code == 404:
                raise RecipeNotFoundException(ref)
            if response.status_code != 200:  # Error message is text
                # To be able to access ret.text (ret.content are bytes)
                response.charset = "utf-8"
                raise get_exception_from_error(response.status_code)(response.text)

    def get_recipe_revision_reference(self, ref):
        # FIXME: implement this new endpoint in the remotes?
        assert ref.revision, "recipe_exists has to be called with a complete reference"
        ref_without_rev = copy.copy(ref)
        ref_without_rev.revision = None
        try:
            remote_refs = self.get_recipe_revisions_references(ref_without_rev)
        except NotFoundException:
            raise RecipeNotFoundException(ref)
        for r in remote_refs:
            if r == ref:
                return r
        raise RecipeNotFoundException(ref)

    def get_package_revision_reference(self, pref):
        # FIXME: implement this endpoint in the remotes?
        assert pref.revision, "get_package_revision_reference has to be called with a complete reference"
        pref_without_rev = copy.copy(pref)
        pref_without_rev.revision = None
        try:
            remote_prefs = self.get_package_revisions_references(pref_without_rev)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        for p in remote_prefs:
            if p == pref:
                return p
        raise PackageNotFoundException(pref)

    def get_recipe_revisions_references(self, ref):
        url = self.router.recipe_revisions(ref)
        tmp = self.get_json(url)["revisions"]
        remote_refs = []
        for item in tmp:
            _tmp = copy.copy(ref)
            _tmp.revision = item.get("revision")
            _tmp.timestamp = from_iso8601_to_timestamp(item.get("time"))
            remote_refs.append(_tmp)

        if ref.revision:  # FIXME: This is a bit messy, is it checking the existance? or getting the time? or both?
            assert "This shoudln't be happening, get_recipe_revisions_references"
        return remote_refs

    def get_latest_recipe_reference(self, ref):
        url = self.router.recipe_latest(ref)
        data = self.get_json(url)
        remote_ref = copy.copy(ref)
        remote_ref.revision = data.get("revision")
        remote_ref.timestamp = from_iso8601_to_timestamp(data.get("time"))
        return remote_ref

    def get_package_revisions_references(self, pref, headers=None):
        url = self.router.package_revisions(pref)
        tmp = self.get_json(url, headers=headers)["revisions"]
        remote_prefs = [PkgReference(pref.ref, pref.package_id, item.get("revision"),
                              from_iso8601_to_timestamp(item.get("time"))) for item in tmp]

        if pref.revision:  # FIXME: This is a bit messy, is it checking the existance? or getting the time? or both?
            for _pref in remote_prefs:
                if _pref.revision == pref.revision:
                    return [_pref]
            raise PackageNotFoundException(pref)
        return remote_prefs

    def get_latest_package_reference(self, pref: PkgReference, headers):
        url = self.router.package_latest(pref)
        data = self.get_json(url, headers=headers)
        remote_pref = copy.copy(pref)
        remote_pref.revision = data.get("revision")
        remote_pref.timestamp = from_iso8601_to_timestamp(data.get("time"))
        return remote_pref
