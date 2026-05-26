import json

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestInstallLockfileConfigRequires:
    """Tests for the alignment check between lockfile config_requires and installed configs."""

    def test_install_no_lockfile(self):
        """conan install without a lockfile skips the check entirely."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.save_home({"config_version.json": json.dumps(
            {"config_version": ["myconf/1.0#aabbcc"]})})
        c.run("install")
        assert "ERROR" not in c.out

    def test_install_empty_lockfile(self):
        """conan install with an empty lockfile skips the check entirely."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                "conan.lock": "{}"})
        c.save_home({"config_version.json": json.dumps(
            {"config_version": ["myconf/1.0#aabbcc"]})})
        c.run("install")
        assert "ERROR" not in c.out

    def test_install_missing_installed_config_error(self):
        """Lockfile with config_requires not installed => Error"""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                "conan.lock": json.dumps({
                    "version": "0.5",
                    "config_requires": ["myconf/1.0#aabbcc", "other/2.1#rev2"]
                })})
        c.run("install . --lockfile=conan.lock", assert_error=True)
        assert ("ERROR: There are config packages in lockfile 'config_requires' "
                "not installed: [myconf/1.0#aabbcc, other/2.1#rev2]") in c.out

    def test_install_missing_installed_config_error_same(self):
        """Same as above but with multiple versions of same package"""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                "conan.lock": json.dumps({
                    "version": "0.5",
                    "config_requires": ["myconf/2.0#aabbcc", "myconf/1.0#aabbcc"]
                })})
        c.run("install . --lockfile=conan.lock", assert_error=True)
        assert ("ERROR: There are config packages in lockfile 'config_requires' "
                "not installed: [myconf/2.0#aabbcc, myconf/1.0#aabbcc]") in c.out

    def test_install_lockfile_config_match(self):
        """Installed config matches lockfile entry -> passes."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                "conan.lock": json.dumps({
                    "version": "0.5",
                    "config_requires": ["myconf/1.0#rev1"]
                })})
        c.save_home({"config_version.json": json.dumps(
            {"config_version": ["myconf/1.0#rev1"]})})
        c.run("install . --lockfile=conan.lock")
        assert "ERROR" not in c.out

    def test_install_lockfile_config_partial_match(self):
        """Lockfile dont lock down to the revision, only version"""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                "conan.lock": json.dumps({
                    "version": "0.5",
                    "config_requires": ["myconf/1.0"]
                })})
        c.save_home({"config_version.json": json.dumps(
            {"config_version": ["myconf/1.0#rev1"]})})
        c.run("install . --lockfile=conan.lock")
        assert "ERROR" not in c.out

    def test_install_lockfile_config_revision_mismatch_error(self):
        """Installed config has different revision than lockfile -> error."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                "conan.lock": json.dumps({
                    "version": "0.5",
                    "config_requires": ["myconf/1.0#rev_in_lockfile"]
                })})
        c.save_home({"config_version.json": json.dumps(
            {"config_version": ["myconf/1.0#rev"]})})
        c.run("install . --lockfile=conan.lock", assert_error=True)
        assert "ERROR: Installed config packages [myconf/1.0#rev] not in the lockfile" in c.out

    def test_install_lockfile_config_version_mismatch(self):
        """Installed config has different version than lockfile entry -> error."""
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
                "conan.lock": json.dumps({
                    "version": "0.5",
                    "config_requires": ["myconf/2.0#aabbcc"]
                })})
        c.save_home({"config_version.json": json.dumps(
            {"config_version": ["myconf/1.0#aabbcc"]})})
        c.run("install . --lockfile=conan.lock", assert_error=True)
        assert "ERROR: Installed config packages [myconf/1.0#aabbcc] not in the lockfile" in c.out
