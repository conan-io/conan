import os

from conan.internal.cache.home_paths import HomePaths

_default_spdx_json = """
def generate_sbom(conanfile, **kwargs):
    d = {}
    return d

"""


def migrate_sbom_file(cache_folder):
    from conans.client.migrations import update_file
    sbom_path = HomePaths(cache_folder).sbom_manifest_plugin_path
    update_file(sbom_path, _default_spdx_json)
