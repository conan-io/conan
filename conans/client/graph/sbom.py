import os

from conan.internal.cache.home_paths import HomePaths

_default_spdx_json = """
todo implement _default_spdx_json
"""

_default_cyclonedx_1_4 = """
todo implement _default_1_4_cyclonedx
"""

def migrate_sbom_files(cache_folder):
    from conans.client.migrations import update_file
    sbom_folder = HomePaths(cache_folder).sbom_manifest_plugin_path
    spdx_json_file = os.path.join(sbom_folder, "spdx.py")
    cyclone_1_4_file = os.path.join(sbom_folder, "cyclonedx.py")
    update_file(spdx_json_file, _default_spdx_json)
    update_file(cyclone_1_4_file, _default_cyclonedx_1_4)
