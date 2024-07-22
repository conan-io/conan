import json
import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestPlatformRequires:
    def test_platform_requires(self):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.0"})
        client.run("create . -pr=profile")
        assert "dep/1.0 - Platform" in client.out

    def test_platform_requires_non_matching(self):
        """ if what is specified in [platform_requires] doesn't match what the recipe requires, then
        the platform_requires will not be used, and the recipe will use its declared version
        """
        client = TestClient(light=True)
        client.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.1"})
        client.run("create dep")
        client.run("create . -pr=profile")
        assert "dep/1.0#6a99f55e933fb6feeb96df134c33af44 - Cache" in client.out

    def test_platform_requires_range(self):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/[>=1.0]"),
                     "profile": "[platform_requires]\ndep/1.1"})
        client.run("create . -pr=profile")
        assert "dep/1.1 - Platform" in client.out

    def test_platform_requires_range_non_matching(self):
        """ if what is specified in [platform_requires] doesn't match what the recipe requires, then
        the platform_requires will not be used, and the recipe will use its declared version
        """
        client = TestClient(light=True)
        client.save({"dep/conanfile.py": GenConanfile("dep", "1.1"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/[>=1.0]"),
                     "profile": "[platform_requires]\ndep/0.1"})
        client.run("create dep")
        client.run("create . -pr=profile")
        assert "dep/1.1#af79f1e3973b7d174e7465038c3f5f36 - Cache" in client.out

    def test_platform_requires_no_host(self):
        """
        platform_requires must not affect tool-requires
        """
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.0"})
        client.run("create . -pr=profile", assert_error=True)
        assert "ERROR: Package 'dep/1.0' not resolved: No remote defined" in client.out

    def test_platform_requires_build_context(self):
        """
        platform_requires must work in the build context too
        """
        client = TestClient(light=True)
        client.save({"tool/conanfile.py": GenConanfile("tool", "1.0").with_requires("dep/1.0"),
                     "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/1.0"),
                     "profile": "[settings]\nos=Linux\n[platform_requires]\ndep/1.0"})
        client.run("create tool -pr:b=profile --build-require")
        assert "dep/1.0 - Platform" in client.out
        client.run("create pkg -pr:b=profile")
        assert "dep/1.0 - Platform" in client.out

    def test_graph_info_platform_requires_range(self):
        """
        graph info doesn't crash
        """
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/[>=1.0]"),
                     "profile": "[platform_requires]\ndep/1.1"})
        client.run("graph info . -pr=profile")
        assert "dep/1.1 - Platform" in client.out

    def test_consumer_resolved_version(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                requires = "dep/[>=1.0]"

                def generate(self):
                    for r, _ in self.dependencies.items():
                        self.output.info(f"DEPENDENCY {r.ref}")
                """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_requires]\ndep/1.1"})
        client.run("install . -pr=profile")
        assert "dep/1.1 - Platform" in client.out
        assert "conanfile.py: DEPENDENCY dep/1.1" in client.out

    def test_consumer_resolved_revision(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                requires = "dep/1.1"

                def generate(self):
                    for r, _ in self.dependencies.items():
                        self.output.info(f"DEPENDENCY {repr(r.ref)}")
                """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_requires]\ndep/1.1#rev1"})
        client.run("install . -pr=profile")
        assert "dep/1.1 - Platform" in client.out
        assert "conanfile.py: DEPENDENCY dep/1.1#rev1" in client.out

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
               requires = "dep/1.1#rev1"

               def generate(self):
                   for r, _ in self.dependencies.items():
                       self.output.info(f"DEPENDENCY {repr(r.ref)}")
               """)
        client.save({"conanfile.py": conanfile})
        client.run("install . -pr=profile")
        assert "dep/1.1 - Platform" in client.out
        assert "conanfile.py: DEPENDENCY dep/1.1#rev1" in client.out

    def test_consumer_unresolved_revision(self):
        """ if a recipe specifies an exact revision and so does the profile
        and it doesn't match, it is an error
        """
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                requires = "dep/1.1#rev2"

                def generate(self):
                    for r, _ in self.dependencies.items():
                        self.output.info(f"DEPENDENCY {repr(r.ref)}")
                """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_requires]\ndep/1.1#rev1"})
        client.run("install . -pr=profile", assert_error=True)
        assert "ERROR: Package 'dep/1.1' not resolved" in client.out

    def test_platform_requires_with_options(self):
        """ https://github.com/conan-io/conan/issues/15685
        """
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.0"})
        client.run("create . -pr=profile -o *:myoption=True")
        assert "dep/1.0 - Platform" in client.out

        conanfile = GenConanfile("pkg", "1.0").with_requirement("dep/1.0",
                                                                options={"dep/1.0:myoption": True})
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_requires]\ndep/1.0"})
        client.run("create . -pr=profile")  # This crashed before for non-existing options
        assert "dep/1.0 - Platform" in client.out


class TestPlatformTestRequires:
    def test_platform_requires(self):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_test_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.0"})
        client.run("create . -pr=profile")
        assert "dep/1.0 - Platform" in client.out


class TestPlatformRequiresLock:

    def test_platform_requires_range(self):
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/[>=1.0]"),
                "profile": "[platform_requires]\ndep/1.1"})
        c.run("lock create . -pr=profile")
        assert "dep/1.1 - Platform" in c.out
        lock = json.loads(c.load("conan.lock"))
        assert lock["requires"] == ["dep/1.1"]

        c.run("install .", assert_error=True)
        assert "Package 'dep/1.1' not resolved: No remote defined" in c.out
        c.run("install . -pr=profile")
        assert "dep/1.1 - Platform" in c.out

        # if the profile points to another version it is an error, not in the lockfile
        c.save({"profile": "[platform_requires]\ndep/1.2"})
        c.run("install . -pr=profile", assert_error=True)
        assert "ERROR: Requirement 'dep/1.2' not in lockfile" in c.out


class TestGenerators:
    def test_platform_requires_range(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "build_type"
                requires = "dep/[>=1.0]"
                generators = "CMakeDeps", # "PkgConfigDeps"
            """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_requires]\ndep/1.1"})
        client.run("install . -pr=profile")
        assert "dep/1.1 - Platform" in client.out
        assert not os.path.exists(os.path.join(client.current_folder, "dep-config.cmake"))
        assert not os.path.exists(os.path.join(client.current_folder, "dep.pc"))


class TestPackageID:
    """ if a consumer depends on recipe revision or package_id what happens
    """

    @pytest.mark.parametrize("package_id_mode", ["recipe_revision_mode", "full_package_mode"])
    def test_package_id_modes(self, package_id_mode):
        """ this test validates that the computation of the downstream consumers package_id
        doesn't break even if it depends on fields not existing in upstream platform_requires, like revision
        or package_id
        """
        client = TestClient(light=True)
        save(client.cache.new_config_path, f"core.package_id:default_unknown_mode={package_id_mode}")
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.0"})
        client.run("create . -pr=profile")
        assert "dep/1.0 - Platform" in client.out

    def test_package_id_explicit_revision(self):
        """
        Changing the platform_requires revision affects consumers if package_revision_mode=recipe_revision
        """
        client = TestClient(light=True)
        save(client.cache.new_config_path, "core.package_id:default_unknown_mode=recipe_revision_mode")
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.0#r1",
                     "profile2": "[platform_requires]\ndep/1.0#r2"})
        client.run("create . -pr=profile")
        assert "dep/1.0#r1 - Platform" in client.out
        assert "pkg/1.0#7ed9bbd2a7c3c4381438c163c93a9f21:" \
               "d9d32dd13cfc9734becc01287570721cd048ba19 - Build" in client.out

        client.run("create . -pr=profile2")
        # pkg gets a new package_id because it is a different revision
        assert "dep/1.0#r2 - Platform" in client.out
        assert "pkg/1.0#7ed9bbd2a7c3c4381438c163c93a9f21:" \
               "2f6bc9cf5015a7210181592d454f36687791a941 - Build" in client.out

    def test_package_id_full_mode(self):
        """
        platform_requires do not have settings or package_id, so it is ignored
        """
        client = TestClient()
        save(client.cache.new_config_path, "core.package_id:default_unknown_mode=full_package_mode")
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
                     "profile": "[platform_requires]\ndep/1.0"})
        client.run("create . -pr=profile -s os=Linux")
        assert "dep/1.0 - Platform" in client.out
        assert "pkg/1.0#7ed9bbd2a7c3c4381438c163c93a9f21:" \
               "f2cfe57716d0a3320019f058edcd728d3379ab32 - Build" in client.out

        client.run("create . -pr=profile -s os=Windows")
        # pkg gets exactly same package_id, changing the settings, do not affect plaform package-id
        assert "dep/1.0 - Platform" in client.out
        assert "pkg/1.0#7ed9bbd2a7c3c4381438c163c93a9f21:" \
               "f2cfe57716d0a3320019f058edcd728d3379ab32 - Build" in client.out
