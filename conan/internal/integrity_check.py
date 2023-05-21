from conan.api.output import ConanOutput
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class IntegrityChecker:
    """
    Check:
        - Performs a corruption integrity check in the cache. This is done by loading the existing
        conanmanifest.txt and comparing against a computed conanmanifest.txt. It
        doesn't address someone tampering with the conanmanifest.txt, just accidental
        modifying of a package contents, like if some file has been added after computing the
        manifest.
        This is to be done over the package contents, not the compressed conan_package.tgz
        artifacts
    """
    def __init__(self, app):
        self._app = app

    def check(self, upload_data):
        corrupted = False
        for ref, recipe_bundle in upload_data.refs():
            corrupted = self._recipe_corrupted(ref) or corrupted
            for pref, prev_bundle in upload_data.prefs(ref, recipe_bundle):
                corrupted = self._package_corrupted(pref) or corrupted
        if corrupted:
            raise ConanException("There are corrupted artifacts, check the error logs")

    def _recipe_corrupted(self, ref: RecipeReference):
        layout = self._app.cache.ref_layout(ref)
        output = ConanOutput()
        read_manifest, expected_manifest = layout.recipe_manifests()

        if read_manifest != expected_manifest:
            output.error(f"{ref}: Manifest mismatch")
            output.error(f"Folder: {layout.export()}")
            diff = read_manifest.difference(expected_manifest)
            for fname, (h1, h2) in diff.items():
                output.error(f"    '{fname}' (manifest: {h1}, file: {h2})")
            return True
        output.info(f"{ref}: Integrity checked: ok")

    def _package_corrupted(self, ref: PkgReference):
        layout = self._app.cache.pkg_layout(ref)
        output = ConanOutput()
        read_manifest, expected_manifest = layout.package_manifests()

        if read_manifest != expected_manifest:
            output.error(f"{ref}: Manifest mismatch")
            output.error(f"Folder: {layout.package()}")
            diff = read_manifest.difference(expected_manifest)
            for fname, (h1, h2) in diff.items():
                output.error(f"    '{fname}' (manifest: {h1}, file: {h2})")
            return True
        output.info(f"{ref}: Integrity checked: ok")
