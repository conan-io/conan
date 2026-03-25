import json
import os

import pytest

from conan.internal.util.files import save
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

# Using the sbom tool with "conan create"
sbom_hook_post_package = """
import json
import os
from conan.errors import ConanException
from conan.api.output import ConanOutput
from conan.tools.sbom import cyclonedx_1_4, cyclonedx_1_6

def post_package(conanfile):
    sbom_cyclonedx_1_4 = cyclonedx_1_4(conanfile, add_build=True, add_tests=True)
    sbom_cyclonedx_1_6 = cyclonedx_1_6(conanfile, add_build=True, add_tests=True)
    with open(os.path.join(conanfile.package_metadata_folder, "sbom14.cdx.json"), 'w') as f:
        json.dump(sbom_cyclonedx_1_4, f, indent=4)
    with open(os.path.join(conanfile.package_metadata_folder, "sbom16.cdx.json"), 'w') as f:
        json.dump(sbom_cyclonedx_1_6, f, indent=4)
"""


class TestCyclonedx:

    @pytest.fixture()
    def hook_setup_post_package_tl(self, transitive_libraries):
        tc = transitive_libraries
        hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
        save(hook_path, sbom_hook_post_package)
        return tc

    @pytest.mark.tool("cmake")
    def test_sbom_generation_create(self, hook_setup_post_package_tl):
        # TODO This doesn't need to be a functional test, check why
        tc = hook_setup_post_package_tl
        tc.run("new cmake_lib -d name=bar -d version=1.0 -d requires=engine/1.0 -f")
        # bar -> engine/1.0 -> matrix/1.0
        tc.run("create . -tf=")
        bar_layout = tc.created_layout()
        assert os.path.exists(os.path.join(bar_layout.metadata(), "sbom14.cdx.json"))
        assert os.path.exists(os.path.join(bar_layout.metadata(), "sbom16.cdx.json"))

    @pytest.mark.tool("cmake")
    @pytest.mark.parametrize("user, channel, user_dep, channel_dep",
                             [("user", None, "user_dep", None),
                              ("user", "channel", "user_dep", "channel_dep")])
    def test_sbom_user_path(self, user, channel, user_dep, channel_dep):
        tc = TestClient(light=True)
        hook_path = os.path.join(tc.paths.hooks_path, "hook_sbom.py")
        save(hook_path, sbom_hook_post_package)
        channel_ref = f"/{channel_dep}" if channel_dep else ""
        tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
                 "conanfile.py": GenConanfile("main", "1.0").with_requires(
                     f"dep/1.0@{user_dep}{channel_ref}")})
        command = "create dep"
        if user:
            command += f" --user={user_dep}"
        if channel:
            command += f" --channel={channel_dep}"

        tc.run(command)

        command = "create ."
        if user:
            command += f" --user={user}"
        if channel:
            command += f" --channel={channel}"
        tc.run(command)

        for version in ("14", "16"):
            create_layout = tc.created_layout()
            cyclone_path = os.path.join(create_layout.metadata(), f"sbom{version}.cdx.json")
            content = tc.load(cyclone_path)
            content_json = json.loads(content)

            assert content_json["components"][0]["bom-ref"].split("&user=")[
                       1] == f"{user}&channel={channel}" if channel else user
            assert content_json["dependencies"][0]["dependsOn"][0].split("&user=")[
                       1] == f"{user_dep}&channel={channel_dep}" if channel_dep else user_dep
