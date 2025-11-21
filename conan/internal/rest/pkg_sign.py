import os

from conan.api.model import PackagesList
from conan.api.output import cli_out_write, Color
from conan.errors import ConanException
from conan.internal.cache.conan_reference_layout import METADATA
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.util.files import mkdir


#FIXME: This is copied from conan.cli.commands.list to avoid circular dependency loading ConanAPI
def print_serial(item, indent=None, color_index=None):
    indent = "" if indent is None else (indent + "  ")
    color_index = 0 if color_index is None else (color_index + 1)
    color_array = [Color.BRIGHT_BLUE, Color.BRIGHT_GREEN, Color.BRIGHT_WHITE,
                   Color.BRIGHT_YELLOW, Color.BRIGHT_CYAN, Color.BRIGHT_MAGENTA, Color.WHITE]
    color = color_array[color_index % len(color_array)]
    if isinstance(item, dict):
        for k, v in item.items():
            if isinstance(v, (str, int)):
                if k.lower() == "error":
                    color = Color.BRIGHT_RED
                    k = "ERROR"
                elif k.lower() == "warning":
                    color = Color.BRIGHT_YELLOW
                    k = "WARN"
                color = Color.BRIGHT_RED if k == "expected" else color
                color = Color.BRIGHT_GREEN if k == "existing" else color
                cli_out_write(f"{indent}{k}: {v}", fg=color)
            else:
                cli_out_write(f"{indent}{k}", fg=color)
                print_serial(v, indent, color_index)
    elif isinstance(item, type([])):
        for elem in item:
            cli_out_write(f"{indent}{elem}", fg=color)
    elif isinstance(item, int):  # Can print 0
        cli_out_write(f"{indent}{item}", fg=color)
    elif item:
        cli_out_write(f"{indent}{item}", fg=color)


def print_graph_package_sign(graph):
    pkg_list = PackagesList()

    for node in graph.nodes:
        if not node.ref:
            continue
        if not node.ref.revision:
            return  # Package sign output does not make sense without revisions

        pkg_list.add_ref(node.ref)

        if node.package_id:
            pkg_list.add_pref(node.pref)

        if node.pkg_sign_recipe:
            pkg_list.recipe_dict(node.ref)["package sign"] = node.pkg_sign_recipe
        if node.package_id and node.pkg_sign_package:
            pkg_list.package_dict(node.pref)["package sign"] = node.pkg_sign_package

    print_cache_sign_verify_text({
        "context": "install",
        "action": "verify",
        "results": pkg_list.serialize(),
    })


def print_cache_sign_verify_text(data):
    def iter_signs(results):
        for ref_data in results.values():
            for revision_data in ref_data.get("revisions", {}).values():
                sign = revision_data.get("package sign")
                if sign:
                    yield sign
                for pkg in revision_data.get("packages", {}).values():
                    for prev in pkg.get("revisions", {}).values():
                        sign = prev.get("package sign")
                        if sign:
                            yield sign

    results_dict = data.get("results", {})
    signs = list(iter_signs(results_dict))
    if not signs:
        return

    action = data.get("action")
    context = data.get("context")
    if context == "cache":
        msg = "Verifying signature of" if action == "verify" else "Signing"
        cli_out_write(f"[Package sign] {msg} packages in local cache...\n")
    else:
        msg = "Verification results" if action == "verify" else "Signing results"
        cli_out_write(f"[Package sign] {msg}:")

    def clean(obj):
        remove_keys = {"info", "timestamp", "files"}
        if not isinstance(obj, dict):
            return obj
        return {k: clean(v) for k, v in obj.items() if k not in remove_keys}

    items = {ref: clean(item) for ref, item in results_dict.items()}
    print_serial(items)

    # Summary
    if context == "cache":
        signs_lower = [s.lower() for s in signs]
        warn = sum("warn" in s for s in signs_lower)
        fail = sum(("fail" in s) or ("error" in s) for s in signs_lower)
        ok = len(signs) - warn - fail
        cli_out_write(f"\n[Package sign] Summary: OK={ok}, WARN={warn}, FAILED={fail}")


class PkgSignaturesPlugin:
    def __init__(self, cache, home_folder):
        self._cache = cache
        self.sign_plugin_path = HomePaths(home_folder).sign_plugin_path
        self._plugin_sign_function = self._plugin_verify_function = None
        self._plugin_file_exists = os.path.isfile(self.sign_plugin_path)
        if self._plugin_file_exists:
            mod, _ = load_python_file(self.sign_plugin_path)
            try:
                self._plugin_sign_function = mod.sign
            except AttributeError:
                pass
            try:
                self._plugin_verify_function = mod.verify
            except AttributeError:
                pass

    def sign(self, pkg_list, context="upload"):  # cache, upload,
        if not self._plugin_file_exists:
            if context == "upload":
                return
            raise ConanException(f"[Package sign] Plugin not configured at {self.sign_plugin_path}")
        if self._plugin_sign_function is None:
            raise ConanException("[Package sign] sign() function not found "
                                 f"in {self.sign_plugin_path}")

        def _sign(ref, files, folder, dict_info, context="upload"):
            metadata_sign = os.path.join(folder, METADATA, "sign")
            mkdir(metadata_sign)
            try:
                result = self._plugin_sign_function(ref,
                                                    artifacts_folder=folder,
                                                    signature_folder=metadata_sign)
                dict_info["package sign"] = result if result is not None else "Created"
                # Add files to the pkglist/bundle
                for f in os.listdir(metadata_sign):
                    files[f"{METADATA}/sign/{f}"] = os.path.join(metadata_sign, f)
            except (ConanException, AssertionError) as e:
                _handle_failure(e, context, dict_info)

        for rref, packages in pkg_list.items():
            recipe_bundle = pkg_list.recipe_dict(rref)
            if recipe_bundle:
                _sign(rref, recipe_bundle.get("files", {}),
                      self._cache.recipe_layout(rref).download_export(), recipe_bundle, context)
            for pref in packages:
                pkg_bundle = pkg_list.package_dict(pref)
                if pkg_bundle:
                    pkg_bundle_files = pkg_bundle["files"] if context == "upload" else {}
                    _sign(pref, pkg_bundle_files, self._cache.pkg_layout(pref).download_package(),
                          pkg_bundle, context)

    def _verify(self, ref, folder, files, dict_info, context="install"):
        metadata_sign = os.path.join(folder, METADATA, "sign")
        try:
            result = self._plugin_verify_function(ref, artifacts_folder=folder,
                                                  signature_folder=metadata_sign, files=files)
            dict_info["package sign"] = result if result is not None else "Verified"
        except (ConanException, AssertionError) as e:
            _handle_failure(e, context, dict_info)

    def verify_ref(self, ref):
        pkg_list = PackagesList()
        pkg_list.add_ref(ref)
        self.verify(pkg_list, context="install")
        return pkg_list.recipe_dict(ref).get("package sign")

    def verify_pref(self, pref):
        pkg_list = PackagesList()
        pkg_list.add_ref(pref.ref)
        pkg_list.add_pref(pref)
        self.verify(pkg_list, context="install")
        return pkg_list.package_dict(pref).get("package sign")

    def verify(self, pkg_list, context="cache"):  # cache, install, upload
        if not self._plugin_file_exists:
            if context == "install":
                return
            raise ConanException(f"[Package sign] Plugin not configured at {self.sign_plugin_path}")
        if self._plugin_verify_function is None:
            raise ConanException("[Package sign] verify() function not found in "
                                 f"{self.sign_plugin_path}")
        for rref, packages in pkg_list.items():
            recipe_bundle = pkg_list.recipe_dict(rref)
            if recipe_bundle:
                rref_folder = self._cache.recipe_layout(rref).download_export()
                self._verify(rref, rref_folder, os.listdir(rref_folder), recipe_bundle, context)
            for pref in packages:
                pkg_bundle = pkg_list.package_dict(pref)
                if pkg_bundle:
                    pref_folder = self._cache.pkg_layout(pref).download_package()
                    self._verify(pref, pref_folder, os.listdir(pref_folder), pkg_bundle, context)


def _handle_failure(exception, context, dict_info):
    exception_msg = str(exception)
    error_msg = f"Failed: {exception_msg}"
    dict_info["package sign"] = error_msg
    if context in ["upload", "install"]:
        raise ConanException(f"[Package sign] {error_msg}")
