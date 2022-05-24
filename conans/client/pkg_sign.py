import os

from conan.cache.conan_reference_layout import METADATA
from conans.client.loader import load_python_file
from conans.util.files import mkdir


class PkgSignaturesPlugin:
    def __init__(self, cache):
        self._cache = cache
        signer = os.path.join(cache.plugins_path, "sign", "sign.py")
        if os.path.isfile(signer):
            mod, _ = load_python_file(signer)
            # TODO: At the moment it requires both methods sign and verify, but that might be relaxed
            self._sign = mod.sign
            self._verify = mod.verify
        else:
            self._sign = self._verify = None

    def sign(self, upload_data):
        if self._sign is None:
            return

        def _sign(ref, files, folder):
            mkdir(folder)
            signatures = self._sign(ref, list(files.values()), folder=folder)
            for signature in signatures:
                files[f"{METADATA}/{signature}"] = f"{folder}/{signature}"

        for recipe in upload_data.recipes:
            if recipe.upload:
                _sign(recipe.ref, recipe.files, self._cache.ref_layout(recipe.ref).recipe_metadata())
            for package in recipe.packages:
                if package.upload:
                    _sign(package.pref, package.files,
                          self._cache.pkg_layout(package.pref).package_metadata())

    def verify(self, ref, files, folder):
        if self._verify is None:
            return
        self._verify(ref, files, folder)
