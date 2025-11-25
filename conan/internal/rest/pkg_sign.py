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
        self._plugin_sign_function = self._plugin_verify_function = None
        if os.path.isfile(signer):
            mod, _ = load_python_file(signer)
            try:
                # TODO: At the moment it requires both methods sign and verify, but that might be relaxed
                self._plugin_sign_function = mod.sign
                self._plugin_verify_function = mod.verify
            except AttributeError:
                pass

    def sign(self, upload_data, from_cache=False):
        if self._plugin_sign_function is None or self._plugin_verify_function is None:
            if not from_cache:
                return
            raise ConanException("[Package sign] Plugin not configured. Both sign() and verify() "
                                 "functions should be defined.")

        def _sign(ref, files, folder):
            metadata_sign = os.path.join(folder, METADATA, "sign")
            mkdir(metadata_sign)
            try:
                result = self._plugin_sign_function(ref, artifacts_folder=folder,
                                                    signature_folder=metadata_sign)
                for f in os.listdir(metadata_sign):
                    files[f"{METADATA}/sign/{f}"] = os.path.join(metadata_sign, f)
            except Exception as e:
                if not from_cache:
                    raise ConanException(f"[Package sign] {e}")
                else:
                    result = f"Failed: {e}"
            return result if result is not None else "Signed"

        for rref, packages in upload_data.items():
            recipe_bundle = upload_data.recipe_dict(rref)
            if recipe_bundle:
                files = recipe_bundle.get("files", {})
                recipe_result = _sign(rref, files, self._cache.recipe_layout(rref).download_export())
                recipe_bundle["package sign"] = recipe_result
            for pref in packages:
                pkg_bundle = upload_data.package_dict(pref)
                if pkg_bundle:
                    files = pkg_bundle.get("files", {})
                    pkg_result = _sign(pref, files, self._cache.pkg_layout(pref).download_package())
                    pkg_bundle["package sign"] = pkg_result

    def verify(self, ref, folder, files, from_cache=False):
        if self._plugin_verify_function is None or self._plugin_sign_function is None:
            if not from_cache:
                return
            raise ConanException("[Package sign] Plugin not configured. Both sign() and verify() "
                                 "functions should be defined.")
        metadata_sign = os.path.join(folder, METADATA, "sign")
        try:
            result = self._plugin_verify_function(ref, artifacts_folder=folder,
                                                  signature_folder=metadata_sign,
                                                  files=files)
        except Exception as e:
            if not from_cache:
                raise ConanException(f"[Package sign] {e}")
            else:
                result = f"Failed: {e}"
        return result if result is not None else "Verified"

    def verify_pkglist(self, pkg_list, from_cache=False):
        for rref, packages in pkg_list.items():
            recipe_bundle = pkg_list.recipe_dict(rref)
            if recipe_bundle:
                rref_folder = self._cache.recipe_layout(rref).download_export()
                recipe_result = self.verify(rref, rref_folder, os.listdir(rref_folder),
                                            from_cache=from_cache)
                recipe_bundle["package sign"] = recipe_result
            for pref in packages:
                pkg_bundle = pkg_list.package_dict(pref)
                if pkg_bundle:
                    pref_folder = self._cache.pkg_layout(pref).download_package()
                    pkg_result = self.verify(pref, pref_folder, os.listdir(pref_folder),
                                             from_cache=from_cache)
                    pkg_bundle["package sign"] = pkg_result
