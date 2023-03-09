import json
import os

from conan.api.output import ConanOutput
from conan.internal.conan_app import ConanApp
from conans.client.cmd.uploader import PackagePreparator, UploadExecutor, UploadUpstreamChecker
from conans.client.pkg_sign import PkgSignaturesPlugin
from conans.errors import ConanException
from conans.util.files import load


class UploadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def check_upstream(self, package_list, remote, force=False):
        """Check if the artifacts are already in the specified remote, skipping them from
        the package_list in that case"""
        app = ConanApp(self.conan_api.cache_folder)
        for ref, bundle in package_list.refs():
            layout = app.cache.ref_layout(ref)
            conanfile_path = layout.conanfile()
            conanfile = app.loader.load_basic(conanfile_path)
            if conanfile.upload_policy == "skip":
                ConanOutput().info(f"{ref}: Skipping upload of binaries, "
                                   "because upload_policy='skip'")
                bundle["packages"] = {}

        UploadUpstreamChecker(app).check(package_list, remote, force)

    def prepare(self, package_list, enabled_remotes):
        """Compress the recipes and packages and fill the upload_data objects
        with the complete information. It doesn't perform the upload nor checks upstream to see
        if the recipe is still there"""
        app = ConanApp(self.conan_api.cache_folder)
        preparator = PackagePreparator(app)
        preparator.prepare(package_list, enabled_remotes)
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
        url = config.get("core.backup_sources:url")
        if url is None:
            return
        download_cache = config.get("tools.files.download:download_cache")
        if download_cache is None:
            raise ConanException("Need to define 'core.download:download_cache'")

        path_backups = os.path.join(download_cache, "s")
        all_refs = {k.repr_notime(): v for k, v in package_list.refs()}
        print("ALL REFS ", all_refs)
        files_to_upload = []
        for f in os.listdir(path_backups):
            print("CHECKING FILE ", f)
            if f.endswith(".json"):
                print("JSON ")
                f = os.path.join(path_backups, f)
                refs = json.loads(load(f))
                print("REFS ", refs)
                if any(ref in all_refs for ref in refs):
                    files_to_upload.append(f)
                    files_to_upload.append(f[:-5])

        print(files_to_upload)
        return files_to_upload
