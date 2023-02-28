import json
import os
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


class TestToolRequires:
    def test_system_tool_require(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/1.0"),
                     "profile": "[system_tools]\ntool/1.0"})
        client.run("create . -pr=profile")
        assert "tool/1.0 - System tool" in client.out

    def test_system_tool_require_non_matching(self):
        """ if what is specified in [system_tool_require] doesn't match what the recipe requires, then
        the system_tool_require will not be used, and the recipe will use its declared version
        """
        client = TestClient()
        client.save({"tool/conanfile.py": GenConanfile("tool", "1.0"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/1.0"),
                     "profile": "[system_tools]\ntool/1.1"})
        client.run("create tool")
        client.run("create . -pr=profile")
        assert "tool/1.0#60ed6e65eae112df86da7f6d790887fd - Cache" in client.out

    def test_system_tool_require_range(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": "[system_tools]\ntool/1.1"})
        client.run("create . -pr=profile")
        assert "tool/1.1 - System tool" in client.out

    def test_system_tool_require_range_non_matching(self):
        """ if what is specified in [system_tool_require] doesn't match what the recipe requires, then
        the system_tool_require will not be used, and the recipe will use its declared version
        """
        client = TestClient()
        client.save({"tool/conanfile.py": GenConanfile("tool", "1.1"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": "[system_tools]\ntool/0.1"})
        client.run("create tool")
        client.run("create . -pr=profile")
        assert "tool/1.1#888bda2348dd2ddcf5960d0af63b08f7 - Cache" in client.out

    def test_system_tool_require_no_host(self):
        """
        system_tools must not affect host context
        """
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("tool/1.0"),
                     "profile": "[system_tools]\ntool/1.0"})
        client.run("create . -pr=profile", assert_error=True)
        assert "ERROR: Package 'tool/1.0' not resolved: No remote defined" in client.out

    def test_graph_info_system_tool_require_range(self):
        """
        graph info doesn't crash
        """
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": "[system_tools]\ntool/1.1"})
        client.run("graph info . -pr=profile")
        assert "tool/1.1 - System tool" in client.out


class TestToolRequiresLock:

    def test_system_tool_require_range(self):
        c = TestClient()
        c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                "profile": "[system_tools]\ntool/1.1"})
        c.run("lock create . -pr=profile")
        assert "tool/1.1 - System tool" in c.out
        lock = json.loads(c.load("conan.lock"))
        assert lock["build_requires"] == ["tool/1.1"]

        c.run("install .", assert_error=True)
        assert "Package 'tool/1.1' not resolved: No remote defined" in c.out
        c.run("install . -pr=profile")
        assert "tool/1.1 - System tool" in c.out

        # even if the profile points to another version the locked one will prevail
        c.save({"profile": "[system_tools]\ntool/1.2"})
        c.run("install . -pr=profile", assert_error=True)
        assert "Package 'tool/1.1' not resolved: No remote defined" in c.out


class TestGenerators:
    def test_system_tool_require_range(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeDeps
            from conan.tools.gnu import PkgConfigDeps

            class Pkg(ConanFile):
                settings = "build_type"
                tool_requires = "tool/[>=1.0]"
                def generate(self):
                    deps = CMakeDeps(self)
                    deps.build_context_activated = ["tool"]
                    deps.generate()
                    deps = PkgConfigDeps(self)
                    deps.build_context_activated = ["tool"]
                    deps.generate()
            """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[system_tools]\ntool/1.1"})
        client.run("install . -pr=profile")
        assert "tool/1.1 - System tool" in client.out
        assert not os.path.exists(os.path.join(client.current_folder, "tool-config.cmake"))
        assert not os.path.exists(os.path.join(client.current_folder, "tool.pc"))


class TestPackageID:
    """ if a consumer depends on recipe revision or package_id what happens
    """

    @pytest.mark.parametrize("package_id_mode", ["recipe_revision_mode", "full_package_mode"])
    def test_package_id_modes(self, package_id_mode):
        """ this test validates that the computation of the downstream consumers package_id
        doesnt break even if it depends on fields not existing in upstream system_tool_require, like revision
        or package_id
        """
        client = TestClient()
        save(client.cache.new_config_path, f"core.package_id:default_build_mode={package_id_mode}")
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("dep/1.0"),
                     "profile": "[system_tools]\ndep/1.0"})
        client.run("create . -pr=profile")
        assert "dep/1.0 - System tool" in client.out

    def test_package_id_explicit_revision(self):
        """
        Changing the system_tool_require revision affects consumers if package_revision_mode=recipe_revision
        """
        client = TestClient()
        save(client.cache.new_config_path, "core.package_id:default_build_mode=recipe_revision_mode")
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("dep/1.0"),
                     "profile": "[system_tools]\ndep/1.0#r1",
                     "profile2": "[system_tools]\ndep/1.0#r2"})
        client.run("create . -pr=profile")
        assert "dep/1.0#r1 - System tool" in client.out
        assert "pkg/1.0#27a56f09310cf1237629bae4104fe5bd:" \
               "ea0e320d94b4b70fcb3efbabf9ab871542f8f696 - Build" in client.out

        client.run("create . -pr=profile2")
        # pkg gets a new package_id because it is a different revision
        assert "dep/1.0#r2 - System tool" in client.out
        assert "pkg/1.0#27a56f09310cf1237629bae4104fe5bd:" \
               "334882884da082740e5a002a0b6fdb509a280159 - Build" in client.out
