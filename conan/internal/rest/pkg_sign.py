import os

from conan.api.output import ConanOutput
from conan.internal.cache.conan_reference_layout import METADATA
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.util.files import mkdir, sha256sum

SIGN_SUMMARY_FILENAME = "sign-summary.json"

SIGN_SUMMARY_CONTENT = {
    "provider": None,
    "method": None,
    "files": {}
}


def is_signed(signature_folder):
    return os.path.exists(os.path.join(signature_folder, SIGN_SUMMARY_FILENAME))


class PkgSignaturesPlugin:
    def __init__(self, cache, home_folder):
        self._cache = cache
        signer = HomePaths(home_folder).sign_plugin_path
        self._plugin_sign_function = self._plugin_verify_function = None
        if os.path.isfile(signer):
            mod, _ = load_python_file(signer)
            try:
                self._plugin_sign_function = mod.sign
            except AttributeError:
                pass
            try:
                self._plugin_verify_function = mod.verify
            except AttributeError:
                pass

    def create_summary(self, files, artifacts_folder):
        checksums = {}
        for fname in os.listdir(artifacts_folder):
            file_path = os.path.join(artifacts_folder, fname)
            if os.path.isfile(file_path):
                sha256 = sha256sum(file_path)
                checksums[fname] = sha256
        sorted_checksums = dict(sorted(checksums.items()))
        content = SIGN_SUMMARY_CONTENT.copy()
        content["files"] = sorted_checksums

    def sign(self, upload_data, action="upload"):  # cache, upload,
        if self._plugin_sign_function is None:
            ConanOutput().error("Package signing plugin: sign function not found")
            return

        def _sign(ref, files, folder):
            metadata_sign = os.path.join(folder, METADATA, "sign")
            mkdir(metadata_sign)
            self._plugin_sign_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                       sign_summary=self.create_summary(folder))

        if action == "upload":
            for rref, recipe_bundle in upload_data.refs().items():
                if recipe_bundle["upload"]:
                    _sign(rref, recipe_bundle["files"], self._cache.recipe_layout(rref).download_export())
                for pref, pkg_bundle in upload_data.prefs(rref, recipe_bundle).items():
                    if pkg_bundle["upload"]:
                        _sign(pref, pkg_bundle["files"], self._cache.pkg_layout(pref).download_package())
        else:
            for rref, recipe_bundle in upload_data.refs().items():
                if recipe_bundle:
                    _sign(rref, [], self._cache.recipe_layout(rref).download_export())
                for pref, pkg_bundle in upload_data.prefs(rref, recipe_bundle).items():
                    if pkg_bundle:
                        _sign(pref, [], self._cache.pkg_layout(pref).download_package())

    def verify(self, ref, folder, files):
        if self._plugin_verify_function is None:
            ConanOutput().error("Package signing plugin: verify function not found")
            return
        metadata_sign = os.path.join(folder, METADATA, "sign")
        self._plugin_verify_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                     files=files)

    def verify_pkglist(self, pkg_list, action="cache"):  # cache, install, upload
        if self._plugin_verify_function is None:
            ConanOutput().error("Package signing plugin: verify function not found")
            return

        for rref, recipe_bundle in pkg_list.refs().items():
            if recipe_bundle:
                rref_folder = self._cache.recipe_layout(rref).download_export()
                self.verify(rref, rref_folder, os.listdir(rref_folder))
            for pref, pkg_bundle in pkg_list.prefs(rref, recipe_bundle).items():
                if pkg_bundle:
                    pref_folder = self._cache.pkg_layout(pref).download_package()
                    self.verify(pref, pref_folder, os.listdir(pref_folder))
