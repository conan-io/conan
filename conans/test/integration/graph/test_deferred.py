import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


class TestToolRequires:
    def test_deferred(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_tool_requires("tool/1.0"),
                     "profile": "[deferred_requires]\ntool/1.0"})
        client.run("create . pkg/1.0@ -pr=profile")
        assert "tool/1.0:357add7d387f11a959f3ee7d4fc9c2487dbaa604 - Deferred" in client.out

    def test_deferred_non_matching(self):
        """ if what is specified in [deferred] doesn't match what the recipe requires, then
        the deferred will not be used, and the recipe will use its declared version
        """
        client = TestClient()
        client.save({"tool/conanfile.py": GenConanfile(),
                     "conanfile.py": GenConanfile().with_tool_requires("tool/1.0"),
                     "profile": "[deferred_requires]\ntool/1.1"})
        client.run("create tool tool/1.0@")
        client.run("create . pkg/1.0@ -pr=profile")
        assert "tool/1.0:357add7d387f11a959f3ee7d4fc9c2487dbaa604 - Cache" in client.out

    def test_deferred_range(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_tool_requires("tool/[>=1.0]"),
                     "profile": "[deferred_requires]\ntool/1.1"})
        client.run("create . pkg/1.0@ -pr=profile")
        assert "tool/1.1:357add7d387f11a959f3ee7d4fc9c2487dbaa604 - Deferred" in client.out

    def test_deferred_range_non_matching(self):
        """ if what is specified in [deferred] doesn't match what the recipe requires, then
        the deferred will not be used, and the recipe will use its declared version
        """
        client = TestClient()
        client.save({"tool/conanfile.py": GenConanfile(),
                     "conanfile.py": GenConanfile().with_tool_requires("tool/[>=1.0]"),
                     "profile": "[deferred_requires]\ntool/0.1"})
        client.run("create tool tool/1.1@")
        client.run("create . pkg/1.0@ -pr=profile")
        assert "tool/1.1:357add7d387f11a959f3ee7d4fc9c2487dbaa604 - Cache" in client.out


class TestRequires:
    """ it works exactly the same for require requires
    """
    def test_deferred(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_requires("tool/1.0"),
                     "profile": "[deferred_requires]\ntool/1.0"})
        client.run("create . pkg/1.0@ -pr=profile")
        assert "tool/1.0:357add7d387f11a959f3ee7d4fc9c2487dbaa604 - Deferred" in client.out


class TestPackageIDModes:
    """ if a consumer depends on recipe revision or package_id what happens
    """

    @pytest.mark.parametrize("package_id_mode", ["recipe_revision_mode", "full_package_mode"])
    def test_package_id_modes(self, package_id_mode):
        client = TestClient()
        save(client.cache.new_config_path, f"core.package_id:default_mode={package_id_mode}")
        client.save({"conanfile.py": GenConanfile().with_requires("dep/1.0"),
                     "profile": "[deferred_requires]\ndep/1.0"})
        client.run("create . pkg/1.0@ -pr=profile")
        assert "dep/1.0:357add7d387f11a959f3ee7d4fc9c2487dbaa604 - Deferred" in client.out
