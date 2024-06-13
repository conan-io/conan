import os
import time
from multiprocessing.pool import ThreadPool

from conan.api.output import ConanOutput
from conan.internal.conan_app import ConanApp
from conan.internal.upload_metadata import gather_metadata
from conans.client.cmd.uploader import PackagePreparator, UploadExecutor, UploadUpstreamChecker
from conans.client.pkg_sign import PkgSignaturesPlugin
from conans.client.rest.file_uploader import FileUploader
from conans.errors import ConanException, AuthenticationException, ForbiddenException


class UploadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def check_upstream(self, package_list, remote, enabled_remotes, force=False):
        """Check if the artifacts are already in the specified remote, skipping them from
        the package_list in that case"""
        app = ConanApp(self.conan_api)
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
        app = ConanApp(self.conan_api)
        preparator = PackagePreparator(app, self.conan_api.config.global_conf)
        preparator.prepare(package_list, enabled_remotes)
        if metadata != ['']:
            gather_metadata(package_list, app.cache, metadata)
        signer = PkgSignaturesPlugin(app.cache, app.cache_folder)
        # This might add files entries to package_list with signatures
        signer.sign(package_list)

    def upload(self, package_list, remote):
        app = ConanApp(self.conan_api)
        app.remote_manager.check_credentials(remote)
        executor = UploadExecutor(app)
        executor.upload(package_list, remote)

    def upload_full(self, package_list, remote, enabled_remotes, check_integrity=False, force=False,
                    metadata=None, dry_run=False):
        """ Does the whole process of uploading, including the possibility of parallelizing
        per recipe based on `core.upload:parallel`:
        - calls check_integrity
        - checks which revision already exist in the server (not necessary to upload)
        - prepare the artifacts to upload (compress .tgz)
        - execute the actual upload
        - upload potential sources backups
        """

        def _upload_pkglist(pkglist, subtitle=lambda _: None):
            if check_integrity:
                subtitle("Checking integrity of cache packages")
                self.conan_api.cache.check_integrity(pkglist)
            # Check if the recipes/packages are in the remote
            subtitle("Checking server existing packages")
            self.check_upstream(pkglist, remote, enabled_remotes, force)
            subtitle("Preparing artifacts for upload")
            self.prepare(pkglist, enabled_remotes, metadata)

            if not dry_run:
                subtitle("Uploading artifacts")
                self.upload(pkglist, remote)
                backup_files = self.conan_api.cache.get_backup_sources(pkglist)
                self.upload_backup_sources(backup_files)

        t = time.time()
        ConanOutput().title(f"Uploading to remote {remote.name}")
        parallel = self.conan_api.config.get("core.upload:parallel", default=1, check_type=int)
        thread_pool = ThreadPool(parallel) if parallel > 1 else None
        if not thread_pool or len(package_list.recipes) <= 1:
            _upload_pkglist(package_list, subtitle=ConanOutput().subtitle)
        else:
            ConanOutput().subtitle(f"Uploading with {parallel} parallel threads")
            thread_pool.map(_upload_pkglist, package_list.split())
        if thread_pool:
            thread_pool.close()
            thread_pool.join()
        elapsed = time.time() - t
        ConanOutput().success(f"Upload completed in {int(elapsed)}s\n")

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

        app = ConanApp(self.conan_api)
        # TODO: verify might need a config to force it to False
        uploader = FileUploader(app.requester, verify=True, config=config, source_credentials=True)
        # TODO: For Artifactory, we can list all files once and check from there instead
        #  of 1 request per file, but this is more general
        for file in files:
            basename = os.path.basename(file)
            full_url = url + basename
            is_summary = file.endswith(".json")
            file_kind = "summary" if is_summary else "file"
            try:
                if is_summary or not uploader.exists(full_url, auth=None):
                    output.info(f"Uploading {file_kind} '{basename}' to backup sources server")
                    uploader.upload(full_url, file, dedup=False, auth=None)
                else:
                    output.info(f"File '{basename}' already in backup sources server, "
                                "skipping upload")
            except (AuthenticationException, ForbiddenException) as e:
                if is_summary:
                    output.warning(f"Could not update summary '{basename}' in backup sources server. "
                                   "Skipping updating file but continuing with upload. "
                                   f"Missing permissions?: {e}")
                else:
                    raise ConanException(f"The source backup server '{url}' needs authentication"
                                         f"/permissions, please provide 'source_credentials.json': {e}")

        output.success("Upload backup sources complete\n")
        return files
