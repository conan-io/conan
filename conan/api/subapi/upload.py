from conan.api.model import UploadBundle
from conan.api.output import ConanOutput
from conan.api.subapi import api_method
from conan.internal.conan_app import ConanApp
from conan.internal.api.select_pattern import SelectPattern
from conans.client.cmd.uploader import IntegrityChecker, PackagePreparator, UploadExecutor, \
    UploadUpstreamChecker
from conans.client.pkg_sign import PkgSignaturesPlugin


class UploadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def get_bundle(self, expression, package_query=None, only_recipe=False):
        ref_pattern = SelectPattern(expression)
        select_bundle = self.conan_api.search.select(ref_pattern, only_recipe, package_query)
        upload_bundle = UploadBundle(select_bundle)

        # This is necessary to upload_policy = "skip"
        app = ConanApp(self.conan_api.cache_folder)
        for ref, bundle in upload_bundle.recipes.items():
            layout = app.cache.ref_layout(ref)
            conanfile_path = layout.conanfile()
            conanfile = app.loader.load_basic(conanfile_path)
            if conanfile.upload_policy == "skip":
                ConanOutput().info(f"{ref}: Skipping upload of binaries, "
                                   "because upload_policy='skip'")
                bundle.packages = []

        return upload_bundle

    @api_method
    def check_integrity(self, upload_data):
        """Check if the recipes and packages are corrupted (it will raise a ConanExcepcion)"""
        app = ConanApp(self.conan_api.cache_folder)
        checker = IntegrityChecker(app)
        checker.check(upload_data)

    @api_method
    def check_upstream(self, upload_bundle, remote, force=False):
        """Check if the artifacts are already in the specified remote, skipping them from
        the upload_bundle in that case"""
        app = ConanApp(self.conan_api.cache_folder)
        UploadUpstreamChecker(app).check(upload_bundle, remote, force)

    @api_method
    def prepare(self, upload_bundle, enabled_remotes):
        """Compress the recipes and packages and fill the upload_data objects
        with the complete information. It doesn't perform the upload nor checks upstream to see
        if the recipe is still there"""
        app = ConanApp(self.conan_api.cache_folder)
        preparator = PackagePreparator(app)
        preparator.prepare(upload_bundle, enabled_remotes)
        signer = PkgSignaturesPlugin(app.cache)
        # This might add files entries to upload_bundle with signatures
        signer.sign(upload_bundle)

    @api_method
    def upload_bundle(self, upload_bundle, remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.remote_manager.check_credentials(remote)
        executor = UploadExecutor(app)
        executor.upload(upload_bundle, remote)
