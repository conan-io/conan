import os

from conan.api.model import PackagesList
from conan.api.output import cli_out_write, Color, ConanOutput
from conan.errors import ConanException
from conan.internal.cache.conan_reference_layout import METADATA
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.util.files import mkdir


def print_graph_package_sign(graph):
    pkg_list = PackagesList()
    for node in graph.nodes:
        if node.ref:
            pkg_list.add_ref(node.ref)

            if node.package_id:
                pkg_list.add_pref(node.pref)

            for rref, packages in pkg_list.items():
                recipe_bundle = pkg_list.recipe_dict(rref)
                if node.pkg_sign_recipe:
                    recipe_bundle["package sign"] = node.pkg_sign_recipe
                for pref in packages:
                    pkg_bundle = pkg_list.package_dict(pref)
                    if node.pkg_sign_package:
                        pkg_bundle["package sign"] = node.pkg_sign_package

    print_cache_sign_verify_text({"context": "install", "action": "verify",
                                  "results": pkg_list.serialize()})


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


def print_cache_sign_verify_text(data):
    action = data.get('action')
    context = data.get('context')
    if context == "cache":
        if action == "verify":
            cli_out_write("[Package sign] Verifying signature of packages in local cache...",
                          endline="\n\n")
        else:
            cli_out_write("[Package sign] Signing packages in local cache...", endline="\n\n")
    else:
        if action == "verify":
            cli_out_write("[Package sign] Verification results:")
        else:
            cli_out_write("[Package sign] Signing results:")

    def format_data(item):
        if isinstance(item, dict):
            result = {}
            for k, v in item.items():
                if isinstance(v, dict):
                    v.pop("info", None)
                    v.pop("timestamp", None)
                    v.pop("files", None)
                result[k] = format_data(v)
            return result
        return item

    items = {ref: format_data(data) for ref, data in data.get("results").items()}

    print_serial(items)

    results = []
    for ref, revisions in data.get("results").items():
        for revision, revision_data in revisions.get("revisions").items():
            results.append(revision_data["package sign"])
            if "packages" in revision_data:
                for package_id, package_data in revision_data["packages"].items():
                    for prev, prev_data in package_data["revisions"].items():
                        results.append(prev_data["package sign"])
    if context == "cache":
        warn_count = 0
        fail_count = 0
        ok_count = 0

        for result in results:
            lower = result.lower()
            if "warn" in lower:
                warn_count += 1
            elif "fail" in lower or "error" in lower:
                fail_count += 1
            else:
                ok_count += 1
        cli_out_write(f"\n[Package sign] Summary: OK={ok_count}, WARN={warn_count}, "
                      f"FAILED={fail_count}")


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
            return
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

    def verify(self, pkg_list, context="cache"):  # cache, install, upload
        if not self._plugin_file_exists:
            return
        if self._plugin_verify_function is None:
            raise ConanException("[Package sign] verify() function not found in "
                                 f"{self.sign_plugin_path}")
        finally_raise = None
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
