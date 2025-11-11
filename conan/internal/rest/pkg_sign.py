import copy
import json
import os

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.cache.conan_reference_layout import METADATA
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.util.files import load, mkdir, save, sha256sum


class PkgSignaturesTools:

    SIGN_SUMMARY_CONTENT = {
        "provider": None,
        "method": None,
        "files": {}
    }
    SIGN_SUMMARY_FILENAME = "sign-summary.json"

    def __init__(self, artifacts_folder, signature_folder):
        self._artifacts_folder = artifacts_folder
        self._signature_folder = signature_folder

    def get_summary_file_path(self):
        return os.path.join(self._signature_folder, self.SIGN_SUMMARY_FILENAME)

    def is_pkg_signed(self):
        try:
            c = self.load_summary()
        except FileNotFoundError:
            return False
        return bool(c.get("provider") and c.get("method"))

    def create_summary_content(self):
        """
        Creates the summary content as a dictionary for manipulation
        @return: Dictionary with the summary content
        """
        checksums = {}
        for fname in os.listdir(self._artifacts_folder):
            file_path = os.path.join(self._artifacts_folder, fname)
            if os.path.isfile(file_path):
                sha256 = sha256sum(file_path)
                checksums[fname] = sha256
        sorted_checksums = dict(sorted(checksums.items()))
        content = copy.deepcopy(self.SIGN_SUMMARY_CONTENT)
        content["files"] = sorted_checksums
        return content

    def load_summary(self):
        """"
        Loads the summary file from the signature folder
        """
        return json.loads(load(self.get_summary_file_path()))

    def save_summary(self, content):
        """
        Saves the content of the summary to the signature folder using SIGN_SUMMARY_FILENAME as the
        file name
        @param content: Content of the summary file
        @return:
        """
        assert content.get("provider")
        assert content.get("method")
        save(self.get_summary_file_path(), json.dumps(content))


class PkgSignaturesPlugin:
    def __init__(self, cache, home_folder):
        self._cache = cache
        self.sign_plugin_path = HomePaths(home_folder).sign_plugin_path
        self._plugin_sign_function = self._plugin_verify_function = None
        if os.path.isfile(self.sign_plugin_path):
            mod, _ = load_python_file(self.sign_plugin_path)
            try:
                self._plugin_sign_function = mod.sign
            except AttributeError:
                pass
            try:
                self._plugin_verify_function = mod.verify
            except AttributeError:
                pass

    def sign(self, upload_data, context="upload"):  # cache, upload,
        results = {}
        if self._plugin_sign_function is None:
            ConanOutput().error(f"[Package signing plugin] sign() function not found in "
                                f"{self.sign_plugin_path}")
            return results

        def _sign(ref, files, folder, context="upload"):
            output = ConanOutput(scope=f"{ref.repr_notime()}")
            metadata_sign = os.path.join(folder, METADATA, "sign")
            mkdir(metadata_sign)
            sign_tools = PkgSignaturesTools(folder, metadata_sign)
            try:
                result = self._plugin_sign_function(ref, artifacts_folder=folder,
                                                    signature_folder=metadata_sign, output=output,
                                                    sign_tools=sign_tools)
            except (ConanException, AssertionError) as e:
                result = _handle_failure(e, context, ref)
            # Add files to the pkglist/bundle
            for f in os.listdir(metadata_sign):
                files[f"{METADATA}/sign/{f}"] = os.path.join(metadata_sign, f)
            return {ref.repr_notime(): result}

        if context == "upload":
            for rref, packages in upload_data.items():
                recipe_bundle = upload_data.recipe_dict(rref)
                if recipe_bundle["upload"]:
                    _sign(rref, recipe_bundle["files"], self._cache.recipe_layout(rref).download_export())
                for pref in packages:
                    pkg_bundle = upload_data.package_dict(pref)
                    if pkg_bundle["upload"]:
                        _sign(pref, pkg_bundle["files"], self._cache.pkg_layout(pref).download_package())
        else:
            for rref, recipe_bundle in upload_data.refs().items():
                if recipe_bundle:
                    result = _sign(rref, {}, self._cache.recipe_layout(rref).download_export(),
                                   context)
                    results.update(result)
                for pref, pkg_bundle in upload_data.prefs(rref, recipe_bundle).items():
                    if pkg_bundle:
                        result = _sign(pref, {}, self._cache.pkg_layout(pref).download_package(),
                                       context)
                        results.update(result)
        return results

    def verify(self, ref, folder, files, context="install"):
        if self._plugin_verify_function is None:
            ConanOutput().error(f"[Package signing plugin] verify() function not found in "
                                f"{self.sign_plugin_path}")
            return {}
        output = ConanOutput(scope=f"{ref.repr_notime()}")
        metadata_sign = os.path.join(folder, METADATA, "sign")
        sign_tools = PkgSignaturesTools(folder, metadata_sign)
        try:
            result = self._plugin_verify_function(ref, artifacts_folder=folder,
                                                  signature_folder=metadata_sign, files=files,
                                                  output=output, sign_tools=sign_tools)
        except (ConanException, AssertionError) as e:
            result = _handle_failure(e, context, ref)
        return {ref.repr_notime(): result}

    def verify_pkglist(self, pkg_list, context="cache"):  # cache, install, upload
        results = {}
        if self._plugin_verify_function is None:
            ConanOutput().error(f"[Package signing plugin] verify() function not found in "
                                f"{self.sign_plugin_path}")
            return results

        for rref, recipe_bundle in pkg_list.refs().items():
            if recipe_bundle:
                rref_folder = self._cache.recipe_layout(rref).download_export()
                result = self.verify(rref, rref_folder, os.listdir(rref_folder), context)
                results.update(result)
            for pref, pkg_bundle in pkg_list.prefs(rref, recipe_bundle).items():
                if pkg_bundle:
                    pref_folder = self._cache.pkg_layout(pref).download_package()
                    result = self.verify(pref, pref_folder, os.listdir(pref_folder), context)
                    results.update(result)
        return results


def _handle_failure(exception, action, ref):
    exception_msg = str(exception)
    if action in ["upload", "install"]:
        # TODO: Mark folder with set_dirty(artifacts_folder)
        raise ConanException(f"{ref.repr_notime()}: {exception_msg}")
    else:
        error_msg = f"Failed: {exception_msg}" if exception_msg else "Failed"
        return error_msg
