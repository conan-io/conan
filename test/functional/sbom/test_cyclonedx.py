import json

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save
import os

# Using the sbom tool with "conan create"
sbom_hook_post_package = """
import json
import os
from conan.errors import ConanException
from conan.api.output import ConanOutput
from conan.tools.sbom import {cyclone_version}

def post_package(conanfile):
    sbom_{cyclone_version} = {cyclone_version}(conanfile, add_build={add_build}, add_tests={add_tests})
    metadata_folder = conanfile.package_metadata_folder
    file_name = "sbom.cdx.json"
    with open(os.path.join(metadata_folder, file_name), 'w') as f:
        json.dump(sbom_{cyclone_version}, f, indent=4)
    ConanOutput().success(f"CYCLONEDX CREATED - {{conanfile.package_metadata_folder}}")
"""


@pytest.mark.parametrize("cyclone_version", ["cyclonedx_1_4", "cyclonedx_1_6"])
class TestCyclonedx:

    @pytest.fixture()
    def hook_setup_post_package(self, cyclone_version):
        tc = TestClient()
        hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
        save(hook_path, sbom_hook_post_package.format(cyclone_version=cyclone_version,
                                                      add_build=True, add_tests=True))
        return tc

    @pytest.fixture()
    def hook_setup_post_package_tl(self, cyclone_version, transitive_libraries):
        tc = transitive_libraries
        hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
        save(hook_path, sbom_hook_post_package.format(cyclone_version=cyclone_version,
                                                      add_build=True, add_tests=True))
        return tc

    @pytest.mark.tool("cmake")
    def test_sbom_generation_create(self, hook_setup_post_package_tl):
        tc = hook_setup_post_package_tl
        tc.run("new cmake_lib -d name=bar -d version=1.0 -d requires=engine/1.0 -f")
        # bar -> engine/1.0 -> matrix/1.0
        tc.run("create . -tf=")
        bar_layout = tc.created_layout()
        assert os.path.exists(os.path.join(bar_layout.metadata(), "sbom.cdx.json"))

    @pytest.mark.tool("cmake")
    @pytest.mark.parametrize("user, channel, user_dep, channel_dep",
                             [("user", None, "user_dep", None),
                              ("user", "channel", "user_dep", "channel_dep")])
    def test_sbom_user_path(self, hook_setup_post_package_tl, user, channel, user_dep, channel_dep):
        tc = hook_setup_post_package_tl
        channel_ref = f"/{channel_dep}" if channel_dep else ""
        tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
                 "conanfile.py": GenConanfile("main", "1.0").with_requires(
                     f"dep/1.0@{user_dep}{channel_ref}")})
        command = "create dep"
        if user: command += f" --user={user_dep}"
        if channel: command += f" --channel={channel_dep}"

        tc.run(command)

        command = "create ."
        if user: command += f" --user={user}"
        if channel: command += f" --channel={channel}"
        tc.run(command)

        create_layout = tc.created_layout()
        cyclone_path = os.path.join(create_layout.metadata(), "sbom.cdx.json")
        content = tc.load(cyclone_path)
        content_json = json.loads(content)

        assert content_json["components"][0]["bom-ref"].split("&user=")[
                   1] == f"{user}&channel={channel}" if channel else user
        assert content_json["dependencies"][0]["dependsOn"][0].split("&user=")[
                   1] == f"{user_dep}&channel={channel_dep}" if channel_dep else user_dep
