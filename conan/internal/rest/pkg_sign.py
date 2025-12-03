import os

from conan.errors import ConanException
from conan.internal.cache.conan_reference_layout import METADATA
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.util.files import mkdir


class PkgSignaturesPlugin:
    def __init__(self, cache, home_folder):
        self._cache = cache
        signer = HomePaths(home_folder).sign_plugin_path
        if os.path.isfile(signer):
            mod, _ = load_python_file(signer)
            # TODO: At the moment it requires both methods sign and verify, but that might be relaxed
            self._plugin_sign_function = getattr(mod, "sign", None)
            self._plugin_verify_function = getattr(mod, "verify", None)
        else:
            self._plugin_sign_function = self._plugin_verify_function = None

    @property
    def is_configured(self):
        return self._plugin_sign_function is not None and self._plugin_verify_function is not None

    def sign_pkg(self, ref, files, folder):
        metadata_sign = os.path.join(folder, METADATA, "sign")
        mkdir(metadata_sign)
        # TODO: Consider creating the package sign summary file by default and check after
        #  calling the plugins' sign function that provider and method fields are filled.
        self._plugin_sign_function(ref, artifacts_folder=folder, signature_folder=metadata_sign)
        for f in os.listdir(metadata_sign):
            files[f"{METADATA}/sign/{f}"] = os.path.join(metadata_sign, f)

    def sign(self, upload_data):
        if self._plugin_sign_function is None:
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
        if self._plugin_verify_function is None:
            return
        metadata_sign = os.path.join(folder, METADATA, "sign")
        self._plugin_verify_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                     files=files)
