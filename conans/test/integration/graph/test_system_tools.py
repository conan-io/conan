import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


class TestToolRequires:
    def test_deferred(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/1.0"),
                     "profile": "[system_tool_requires]\ntool/1.0"})
        client.run("create . -pr=profile")
        assert "tool/1.0 - System tool" in client.out

    def test_deferred_non_matching(self):
        """ if what is specified in [deferred] doesn't match what the recipe requires, then
        the deferred will not be used, and the recipe will use its declared version
        """
        client = TestClient()
        client.save({"tool/conanfile.py": GenConanfile("tool", "1.0"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/1.0"),
                     "profile": "[system_tool_requires]\ntool/1.1"})
        client.run("create tool")
        client.run("create . -pr=profile")
        assert "tool/1.0#60ed6e65eae112df86da7f6d790887fd - Cache" in client.out

    def test_deferred_range(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": "[system_tool_requires]\ntool/1.1"})
        client.run("create . -pr=profile")
        assert "tool/1.1 - System tool" in client.out

    def test_deferred_range_non_matching(self):
        """ if what is specified in [deferred] doesn't match what the recipe requires, then
        the deferred will not be used, and the recipe will use its declared version
        """
        client = TestClient()
        client.save({"tool/conanfile.py": GenConanfile("tool", "1.1"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": "[system_tool_requires]\ntool/0.1"})
        client.run("create tool")
        client.run("create . -pr=profile")
        assert "tool/1.1#888bda2348dd2ddcf5960d0af63b08f7 - Cache" in client.out


class TestRequires:
    """ it works exactly the same for require requires
    """
    def test_deferred(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("tool/1.0"),
                     "profile": "[system_tool_requires]\ntool/1.0"})
        client.run("create . -pr=profile", assert_error=True)
        assert "ERROR: Package 'tool/1.0' not resolved: No remote defined" in client.out


class TestPackageID:
    """ if a consumer depends on recipe revision or package_id what happens
    """

    @pytest.mark.parametrize("package_id_mode", ["recipe_revision_mode", "full_package_mode"])
    def test_package_id_modes(self, package_id_mode):
        """ this test validates that the computation of the downstream consumers package_id
        doesnt break even if it depends on fields not existing in upstream deferred, like revision
        or package_id
        """
        client = TestClient()
        save(client.cache.new_config_path, f"core.package_id:default_build_mode={package_id_mode}")
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("dep/1.0"),
                     "profile": "[system_tool_requires]\ndep/1.0"})
        client.run("create . -pr=profile")
        assert "dep/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709 - System tool" in client.out

    def test_package_id_explicit_revision(self):
        """
        Changing the deferred revision affects consumers if package_revision_mode=recipe_revision
        """
        client = TestClient()
        save(client.cache.new_config_path, "core.package_id:default_build_mode=recipe_revision_mode")
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("dep/1.0"),
                     "profile": "[system_tool_requires]\ndep/1.0#r1",
                     "profile2": "[system_tool_requires]\ndep/1.0#r2"})
        client.run("create . -pr=profile")
        assert "dep/1.0#r1:da39a3ee5e6b4b0d3255bfef95601890afd80709 - System tool" in client.out
        assert "pkg/1.0#27a56f09310cf1237629bae4104fe5bd:" \
               "ea0e320d94b4b70fcb3efbabf9ab871542f8f696 - Build" in client.out

        client.run("create . -pr=profile2")
        # pkg gets a new package_id because it is a different revision
        assert "dep/1.0#r2:da39a3ee5e6b4b0d3255bfef95601890afd80709 - System tool" in client.out
        assert "pkg/1.0#27a56f09310cf1237629bae4104fe5bd:" \
               "334882884da082740e5a002a0b6fdb509a280159 - Build" in client.out
