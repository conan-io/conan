import os

from conan.api.output import ConanOutput
from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanApp
from conan.internal.upload_metadata import gather_metadata
from conans.client.cmd.uploader import PackagePreparator, UploadExecutor, UploadUpstreamChecker
from conans.client.downloaders.download_cache import DownloadCache
from conans.client.pkg_sign import PkgSignaturesPlugin
from conans.client.rest.file_uploader import FileUploader
from conans.errors import ConanException, AuthenticationException, ForbiddenException


class UploadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def check_upstream(self, package_list, remote, enabled_remotes, force=False):
        """Check if the artifacts are already in the specified remote, skipping them from
        the package_list in that case"""
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        for ref, bundle in package_list.refs().items():
            layout = app.cache.recipe_layout(ref)
            conanfile_path = layout.conanfile()
            conanfile = app.loader.load_basic(conanfile_path, remotes=enabled_remotes)
            if conanfile.upload_policy == "skip":
                ConanOutput().info(f"{ref}: Skipping upload of binaries, "
                                   "because upload_policy='skip'")
                bundle["packages"] = {}

        UploadUpstreamChecker(app).check(package_list, remote, force)

    def prepare(self, package_list, enabled_remotes, metadata=None):
        """Compress the recipes and packages and fill the upload_data objects
        with the complete information. It doesn't perform the upload nor checks upstream to see
        if the recipe is still there
        :param package_list:
        :param enabled_remotes:
        :param metadata: A list of patterns of metadata that should be uploaded. Default None
        means all metadata will be uploaded together with the pkg artifacts. If metadata is empty
        string (""), it means that no metadata files should be uploaded."""
        if metadata and metadata != [''] and '' in metadata:
            raise ConanException("Empty string and patterns can not be mixed for metadata.")
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        preparator = PackagePreparator(app, self.conan_api.config.global_conf)
        preparator.prepare(package_list, enabled_remotes)
        if metadata != ['']:
            gather_metadata(package_list, app.cache, metadata)
        signer = PkgSignaturesPlugin(app.cache)
        # This might add files entries to package_list with signatures
        signer.sign(package_list)

    def upload(self, package_list, remote):
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        app.remote_manager.check_credentials(remote)
        executor = UploadExecutor(app)
        executor.upload(package_list, remote)

    def get_backup_sources(self, package_list=None):
        """Get list of backup source files currently present in the cache,
        either all of them if no argument, else filter by those belonging to the references in the package_list"""
        config = self.conan_api.config.global_conf
        download_cache_path = config.get("core.sources:download_cache")
        download_cache_path = download_cache_path or HomePaths(
            self.conan_api.cache_folder).default_sources_backup_folder
        excluded_urls = config.get("core.sources:exclude_urls", check_type=list, default=[])
        download_cache = DownloadCache(download_cache_path)
        return download_cache.get_backup_sources_files_to_upload(excluded_urls, package_list)

    def upload_backup_sources(self, files):
        config = self.conan_api.config.global_conf
        url = config.get("core.sources:upload_url", check_type=str)
        if url is None:
            return
        url = url if url.endswith("/") else url + "/"

        output = ConanOutput()
        output.subtitle("Uploading backup sources")
        if not files:
            output.info("No backup sources files to upload")
            return files

        app = ConanApp(self.conan_api.cache_folder, config)
        # TODO: verify might need a config to force it to False
        uploader = FileUploader(app.requester, verify=True, config=config)
        # TODO: For Artifactory, we can list all files once and check from there instead
        #  of 1 request per file, but this is more general
        for file in files:
            basename = os.path.basename(file)
            full_url = url + basename
            try:
                # Always upload summary .json but only upload blob if it does not already exist
                if file.endswith(".json") or not uploader.exists(full_url, auth=None):
                    output.info(f"Uploading file '{basename}' to backup sources server")
                    uploader.upload(full_url, file, dedup=False, auth=None)
                else:
                    output.info(f"File '{basename}' already in backup sources server, "
                                "skipping upload")
            except (AuthenticationException, ForbiddenException) as e:
                raise ConanException(f"The source backup server '{url}' needs authentication"
                                     f"/permissions, please provide 'source_credentials.json': {e}")

        output.success("Upload backup sources complete\n")
        return files
