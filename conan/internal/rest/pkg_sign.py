import os

from conan.internal.cache.conan_reference_layout import METADATA
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.util.files import mkdir
from conan.tools.pkg_signing.plugin import (get_manifest_filepath, get_signatures_filepath,
                                            _save_manifest, _save_signatures, PKGSIGN_MANIFEST,
                                            PKGSIGN_SIGNATURES, _verify_files_checksums)


class PkgSignaturesPlugin:
    def __init__(self, cache, home_folder):
        self._cache = cache
        signer = HomePaths(home_folder).sign_plugin_path
        if os.path.isfile(signer):
            mod, _ = load_python_file(signer)
            self._plugin_sign_function = getattr(mod, "sign", None)
            self._plugin_verify_function = getattr(mod, "verify", None)
        else:
            self._plugin_sign_function = self._plugin_verify_function = None

    @property
    def is_sign_configured(self):
        return self._plugin_sign_function is not None

    @property
    def is_verify_configured(self):
        return self._plugin_verify_function is not None

    def sign_pkg(self, ref, files, folder):
        metadata_sign = os.path.join(folder, METADATA, "sign")
        mkdir(metadata_sign)
        # Generate the package sign manifest before calling the plugin
        _save_manifest(folder, metadata_sign)
        signatures = self._plugin_sign_function(ref, artifacts_folder=folder,
                                                signature_folder=metadata_sign)
        # Save signatures file with the plugin's returned signatures data
        _save_signatures(metadata_sign, signatures)
        # Add files to package bundle so they get uploaded
        files[f"{METADATA}/sign/{PKGSIGN_MANIFEST}"] = get_manifest_filepath(metadata_sign)
        files[f"{METADATA}/sign/{PKGSIGN_SIGNATURES}"] = get_signatures_filepath(metadata_sign)
        for sig in signatures:
            for name, file in sig.get("sign_artifacts", {}).items():
                #TODO: print output?
                files[f"{METADATA}/sign/{file}"] = os.path.join(metadata_sign, file)

    def sign(self, upload_data):
        if not self.is_sign_configured:
            return

        for rref, packages in upload_data.items():
            recipe_bundle = upload_data.recipe_dict(rref)
            if recipe_bundle["upload"]:
                self.sign_pkg(rref, recipe_bundle["files"],
                              self._cache.recipe_layout(rref).download_export())
            for pref in packages:
                pkg_bundle = upload_data.package_dict(pref)
                if pkg_bundle["upload"]:
                    self.sign_pkg(pref, pkg_bundle["files"],
                                  self._cache.pkg_layout(pref).download_package())

    def verify(self, ref, folder, files):
        if not self.is_verify_configured:
            return
        metadata_sign = os.path.join(folder, METADATA, "sign")
        _verify_files_checksums(metadata_sign, files)  # Verify package files checksums before calling the plugin
        self._plugin_verify_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                     files=files)
