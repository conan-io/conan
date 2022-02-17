from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.source import retrieve_exports_sources
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class DownloadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def recipe(self, ref: RecipeReference, remote: Remote):
        output = ConanOutput()
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])
        skip_download = app.cache.exists_rrev(ref)
        if skip_download:
            output.info(f"Skip {ref.repr_notime()} download, already in cache")
            return False

        output.info(f"Downloading {ref.repr_notime()}")
        app.remote_manager.get_recipe(ref, remote)

        layout = app.cache.ref_layout(ref)
        conan_file_path = layout.conanfile()
        conanfile = app.loader.load_basic(conan_file_path, display=ref)

        # Download the sources too, don't be lazy
        output.info(f"Downloading {str(ref)} sources")
        retrieve_exports_sources(app.remote_manager, layout, conanfile, ref, [remote])
        return True

    @api_method
    def package(self, pref: PkgReference, remote: Remote):
        output = ConanOutput()
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])
        if not app.cache.exists_rrev(pref.ref):
            raise ConanException("The recipe of the specified package "
                                 "doesn't exist, download it first")

        skip_download = app.cache.exists_prev(pref)
        if skip_download:
            output.info(f"Skip {pref.repr_notime()} download, already in cache")
            return False
        layout = app.cache.ref_layout(pref.ref)
        conan_file_path = layout.conanfile()
        conanfile = app.loader.load_basic(conan_file_path, display=pref.ref)
        output.info(f"Downloading {pref.repr_notime()}")
        app.remote_manager.get_package(conanfile, pref, remote)
        return True
