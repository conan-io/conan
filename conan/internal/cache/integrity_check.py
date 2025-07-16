import os

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.api.model import PkgReference
from conan.api.model import RecipeReference
from conan.internal.rest.pkg_sign import PkgSignaturesPlugin


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
    def __init__(self, cache, home_folder):
        self._cache = cache
        self._pkg_signatures_plugin = PkgSignaturesPlugin(cache, home_folder)

    def check(self, pkg_list, check_corrupted=True, check_package_signing=True):
        assert check_corrupted or check_package_signing, \
            "Integrity checked should perform at least one check"
        corrupted = False
        invalid_signature = False
        for ref, recipe_bundle in pkg_list.refs().items():
            if check_corrupted:
                corrupted = self._recipe_corrupted(ref) or corrupted
            if check_package_signing:
                invalid_signature = self._ref_invalid_signature(ref) or invalid_signature
            for pref, prev_bundle in pkg_list.prefs(ref, recipe_bundle).items():
                if check_corrupted:
                    corrupted = self._package_corrupted(pref) or corrupted
                if check_package_signing:
                    invalid_signature = self._ref_invalid_signature(pref) or invalid_signature
        msgs = []
        if corrupted:
            msgs.append("There are corrupted artifacts.")
        if invalid_signature:
            msgs.append("There are artifacts with invalid signature.")
        if corrupted or invalid_signature:
            msgs.append("Check the error logs.")
            raise ConanException(" ".join(msgs))

    def _ref_invalid_signature(self, ref):
        output = ConanOutput(scope=f"{ref.repr_notime()} [Package-signing plugin]")
        is_recipe = isinstance(ref, RecipeReference)
        layout = self._cache.recipe_layout(ref) if is_recipe else self._cache.pkg_layout(ref)
        folder = layout.download_export() if is_recipe else layout.download_package()
        files = os.listdir(folder)
        try:
            self._pkg_signatures_plugin.verify(ref, folder, files)
        except (ConanException, AssertionError) as e:
            output.error("Error verifying package signature",
                         error_type="exception")
            output.error(str(e), error_type="exception")
            return True

    def _recipe_corrupted(self, ref: RecipeReference):
        layout = self._cache.recipe_layout(ref)
        output = ConanOutput(scope=f"{ref.repr_notime()}")
        try:
            read_manifest, expected_manifest = layout.recipe_manifests()
        except FileNotFoundError:
            output.error("Manifest missing", error_type="exception")
            return True
        # Filter exports_sources from read manifest if there are no exports_sources locally
        # This happens when recipe is downloaded without sources (not built from source)
        export_sources_folder = layout.export_sources()
        if not os.path.exists(export_sources_folder):
            read_manifest.file_sums = {k: v for k, v in read_manifest.file_sums.items()
                                       if not k.startswith("export_source")}

        if read_manifest != expected_manifest:
            output_lines = ["", "Manifest mismatch", f"    Folder: {layout.package()}"]
            diff = read_manifest.difference(expected_manifest)
            for fname, (h1, h2) in diff.items():
                output_lines.append(f"        {fname} (manifest: {h1}, file: {h2})")
            output.error("\n".join(output_lines), error_type="exception")
            return True
        output.info("Integrity check: ok")

    def _package_corrupted(self, ref: PkgReference):
        layout = self._cache.pkg_layout(ref)
        output = ConanOutput(scope=f"{ref.repr_notime()}")
        try:
            read_manifest, expected_manifest = layout.package_manifests()
        except FileNotFoundError:
            output.error("Manifest missing", error_type="exception")
            return True

        if read_manifest != expected_manifest:
            output_lines = ["", "Manifest mismatch", f"    Folder: {layout.package()}"]
            diff = read_manifest.difference(expected_manifest)
            for fname, (h1, h2) in diff.items():
                output_lines.append(f"        {fname} (manifest: {h1}, file: {h2})")
            output.error("\n".join(output_lines), error_type="exception")
            return True
        output.info("Integrity check: ok")
