from conan.api.output import ConanOutput
from conan.internal.conan_app import ConanApp
from conans.client.cmd.uploader import PackagePreparator, UploadExecutor, UploadUpstreamChecker
from conans.client.pkg_sign import PkgSignaturesPlugin


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
