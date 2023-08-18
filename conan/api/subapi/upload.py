import os

from conan.api.output import ConanOutput
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
        app = ConanApp(self.conan_api.cache_folder)
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
        means all metadata will be uploaded together with the pkg artifacts"""
        app = ConanApp(self.conan_api.cache_folder)
        preparator = PackagePreparator(app)
        preparator.prepare(package_list, enabled_remotes)
        gather_metadata(package_list, app.cache, metadata)
        signer = PkgSignaturesPlugin(app.cache)
        # This might add files entries to package_list with signatures
        signer.sign(package_list)

    def upload(self, package_list, remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.remote_manager.check_credentials(remote)
        executor = UploadExecutor(app)
        executor.upload(package_list, remote)

    def upload_backup_sources(self, package_list):
        app = ConanApp(self.conan_api.cache_folder)
        config = app.cache.new_config
        url = config.get("core.sources:upload_url")
        if url is None:
            return
        url = url if url.endswith("/") else url + "/"
        download_cache_path = config.get("core.sources:download_cache")
        download_cache_path = download_cache_path or app.cache.default_sources_backup_folder
        excluded_urls = config.get("core.sources:exclude_urls", check_type=list, default=[])

        files = DownloadCache(download_cache_path).get_backup_sources_files_to_upload(package_list,
                                                                                      excluded_urls)
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
                    ConanOutput().info(f"Uploading file '{basename}' to backup sources server")
                    uploader.upload(full_url, file, dedup=False, auth=None)
                else:
                    ConanOutput().info(f"File '{basename}' already in backup sources server, "
                                       "skipping upload")
            except (AuthenticationException, ForbiddenException) as e:
                raise ConanException(f"The source backup server '{url}' needs authentication"
                                     f"/permissions, please provide 'source_credentials.json': {e}")
        return files
