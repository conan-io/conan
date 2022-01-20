from conans.cli.api.model import UploadBundle
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.cmd.uploader import UploadChecker, PackagePreparator, UploadExecutor
from conans.errors import ConanException


class UploadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def get_bundle(self, expression, package_query=None, only_recipe=False):
        ret = UploadBundle()
        if ":" in expression or package_query:
            # We are uploading the selected packages and the recipes belonging to that
            prefs = self.conan_api.search.package_revisions(expression, query=package_query)
            if not prefs:
                raise ConanException("There are no packages matching {}".format(expression))
            ret.add_prefs(prefs)
        else:
            # Upload the recipes and all the packages
            refs = self.conan_api.search.recipe_revisions(expression)
            if only_recipe:
                for ref in refs:
                    ret.add_ref(ref)
                return ret
            app = ConanApp(self.conan_api.cache_folder)
            for ref in refs:
                # Get all the prefs and all the prevs
                pkg_ids = app.cache.get_package_references(ref, only_latest_prev=False)
                if pkg_ids:
                    ret.add_prefs(pkg_ids)
                else:
                    ret.add_ref(ref)
        return ret

    @api_method
    def check_integrity(self, upload_data):
        app = ConanApp(self.conan_api.cache_folder)
        checker = UploadChecker(app)
        checker.check(upload_data)

    @api_method
    def simulate(self, upload_data, remote, force=False):
        """Compress the recipes and packages and fill the upload_data objects
        with the complete information. It doesn't perform the upload"""
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])
        preparator = PackagePreparator(app)
        preparator.prepare(upload_data, remote, force)

    @api_method
    def upload_bundle(self, upload_bundle, remote, force=False):
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])
        preparator = PackagePreparator(app)
        preparator.prepare(upload_bundle, remote, force)

        app.remote_manager.check_credentials(remote)
        executor = UploadExecutor(app)
        executor.upload(upload_bundle, remote, force)

