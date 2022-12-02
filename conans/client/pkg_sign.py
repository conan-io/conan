import os

from conan.internal.cache.conan_reference_layout import METADATA
from conans.client.loader import load_python_file
from conans.util.files import mkdir


class PkgSignaturesPlugin:
    def __init__(self, cache):
        self._cache = cache
        signer = os.path.join(cache.plugins_path, "sign", "sign.py")
        if os.path.isfile(signer):
            mod, _ = load_python_file(signer)
            # TODO: At the moment it requires both methods sign and verify, but that might be relaxed
            self._plugin_sign_function = mod.sign
            self._plugin_verify_function = mod.verify
        else:
            self._plugin_sign_function = self._plugin_verify_function = None

    def sign(self, upload_data):
        if self._plugin_sign_function is None:
            return

        def _sign(ref, files, folder):
            metadata_sign = os.path.join(folder, METADATA, "sign")
            mkdir(metadata_sign)
            self._plugin_sign_function(ref, artifacts_folder=folder, signature_folder=metadata_sign)
            for f in os.listdir(metadata_sign):
                files[f"{METADATA}/sign/{f}"] = os.path.join(metadata_sign, f)

        for ref, bundle in upload_data.recipes.items():
            if bundle.upload:
                _sign(ref, bundle.files, self._cache.ref_layout(ref).download_export())
            for package in bundle.packages:
                if package.upload:
                    _sign(package.pref, package.files,
                          self._cache.pkg_layout(package.pref).download_package())

    def verify(self, ref, folder):
        if self._plugin_verify_function is None:
            return
        metadata_sign = os.path.join(folder, METADATA, "sign")
        self._plugin_verify_function(ref, artifacts_folder=folder, signature_folder=metadata_sign)
