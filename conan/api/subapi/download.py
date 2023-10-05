from conan.api.model import Remote
from conan.api.output import ConanOutput
from conan.internal.conan_app import ConanApp
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class DownloadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def recipe(self, ref: RecipeReference, remote: Remote, metadata=None):
        output = ConanOutput()
        app = ConanApp(self.conan_api.cache_folder)
        assert ref.revision, f"Reference '{ref}' must have revision"
        try:
            app.cache.recipe_layout(ref)  # raises if not found
        except ConanException:
            pass
        else:
            output.info(f"Skip recipe {ref.repr_notime()} download, already in cache")
            if metadata:
                app.remote_manager.get_recipe_metadata(ref, remote, metadata)
            return False

        output.info(f"Downloading recipe '{ref.repr_notime()}'")
        if ref.timestamp is None:  # we didnt obtain the timestamp before (in general it should be)
            # Respect the timestamp of the server, the ``get_recipe()`` doesn't do it internally
            # Best would be that ``get_recipe()`` returns the timestamp in the same call
            server_ref = app.remote_manager.get_recipe_revision_reference(ref, remote)
            assert server_ref == ref
            ref.timestamp = server_ref.timestamp
        app.remote_manager.get_recipe(ref, remote, metadata)

        # Download the sources too, don't be lazy
        output.info(f"Downloading '{str(ref)}' sources")
        recipe_layout = app.cache.recipe_layout(ref)
        app.remote_manager.get_recipe_sources(ref, recipe_layout, remote)
        return True

    def package(self, pref: PkgReference, remote: Remote, metadata=None):
        output = ConanOutput()
        app = ConanApp(self.conan_api.cache_folder)
        try:
            app.cache.recipe_layout(pref.ref)  # raises if not found
        except ConanException:
            raise ConanException("The recipe of the specified package "
                                 "doesn't exist, download it first")

        skip_download = app.cache.exists_prev(pref)
        if skip_download:
            output.info(f"Skip package {pref.repr_notime()} download, already in cache")
            if metadata:
                app.remote_manager.get_package_metadata(pref, remote, metadata)
            return False

        if pref.timestamp is None:  # we didnt obtain the timestamp before (in general it should be)
            # Respect the timestamp of the server
            server_pref = app.remote_manager.get_package_revision_reference(pref, remote)
            assert server_pref == pref
            pref.timestamp = server_pref.timestamp

        output.info(f"Downloading package '{pref.repr_notime()}'")
        app.remote_manager.get_package(pref, remote, metadata)
        return True
