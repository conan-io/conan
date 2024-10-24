import os

from conan.internal.cache.home_paths import HomePaths

_default_spdx_json = """
def generate_sbom(conan_api, graph):
    d = {}
    return d

"""


def migrate_sbom_files(cache_folder):
    from conans.client.migrations import update_file
    sbom_folder = HomePaths(cache_folder).sbom_manifest_plugin_path
    spdx_json_file = os.path.join(sbom_folder, "spdx_json.py")
    update_file(spdx_json_file, _default_spdx_json)
