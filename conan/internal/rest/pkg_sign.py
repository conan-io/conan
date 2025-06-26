import os

from conan.api.output import ConanOutput
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
                self._plugin_sign_function = mod.sign
                self._plugin_verify_function = mod.verify
            except AttributeError:
                pass

    def sign(self, upload_data):
        if self._plugin_sign_function is None:
            return

        def _sign(ref, files, folder):
            output = ConanOutput(scope=f"{ref.repr_notime()}")
            metadata_sign = os.path.join(folder, METADATA, "sign")
            mkdir(metadata_sign)
            self._plugin_sign_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                       output=output)
            for f in os.listdir(metadata_sign):
                files[f"{METADATA}/sign/{f}"] = os.path.join(metadata_sign, f)

        for rref, recipe_bundle in upload_data.refs().items():
            if recipe_bundle["upload"]:
                _sign(rref, recipe_bundle["files"], self._cache.recipe_layout(rref).download_export())
            for pref, pkg_bundle in upload_data.prefs(rref, recipe_bundle).items():
                if pkg_bundle["upload"]:
                    _sign(pref, pkg_bundle["files"], self._cache.pkg_layout(pref).download_package())

    def verify(self, ref, folder, files):
        output = ConanOutput(scope=f"{ref.repr_notime()}")
        if self._plugin_verify_function is None:
            return
        metadata_sign = os.path.join(folder, METADATA, "sign")
        self._plugin_verify_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                     files=files, output=output)
