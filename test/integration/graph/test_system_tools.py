import json
import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestToolRequires:
    @pytest.mark.parametrize("revision", ["", "#myrev"])
    def test_system_tool_require(self, revision):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/1.0"),
                     "profile": f"[platform_tool_requires]\ntool/1.0{revision}"})
        client.run("create . -pr=profile")
        assert f"tool/1.0{revision or '#platform'} - Platform" in client.out

    def test_system_tool_require_non_matching(self):
        """ if what is specified in [platform_tool_requires] doesn't match what the recipe requires, then
        the platform_tool_requires will not be used, and the recipe will use its declared version
        """
        client = TestClient(light=True)
        client.save({"tool/conanfile.py": GenConanfile("tool", "1.0"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/1.0"),
                     "profile": "[platform_tool_requires]\ntool/1.1"})
        client.run("create tool")
        client.run("create . -pr=profile")
        assert "tool/1.0#60ed6e65eae112df86da7f6d790887fd - Cache" in client.out

    @pytest.mark.parametrize("revision", ["", "#myrev"])
    def test_system_tool_require_range(self, revision):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": f"[platform_tool_requires]\ntool/1.1{revision}"})
        client.run("create . -pr=profile")
        assert f"tool/1.1{revision or '#platform'} - Platform" in client.out

    def test_system_tool_require_range_non_matching(self):
        """ if what is specified in [system_tool_require] doesn't match what the recipe requires, then
        the system_tool_require will not be used, and the recipe will use its declared version
        """
        client = TestClient(light=True)
        client.save({"tool/conanfile.py": GenConanfile("tool", "1.1"),
                     "conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": "[platform_tool_requires]\ntool/0.1"})
        client.run("create tool")
        client.run("create . -pr=profile")
        assert "tool/1.1#888bda2348dd2ddcf5960d0af63b08f7 - Cache" in client.out

    def test_system_tool_require_no_host(self):
        """
        system_tools must not affect host context
        """
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_requires("tool/1.0"),
                     "profile": "[platform_tool_requires]\ntool/1.0"})
        client.run("create . -pr=profile", assert_error=True)
        assert "ERROR: Package 'tool/1.0' not resolved: No remote defined" in client.out

    def test_graph_info_system_tool_require_range(self):
        """
        graph info doesn't crash
        """
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                     "profile": "[platform_tool_requires]\ntool/1.1"})
        client.run("graph info . -pr=profile")
        assert "tool/1.1 - Platform" in client.out

    def test_consumer_resolved_version(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                tool_requires = "tool/[>=1.0]"

                def generate(self):
                    for r, _ in self.dependencies.items():
                        self.output.info(f"DEPENDENCY {r.ref}")
                """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_tool_requires]\ntool/1.1"})
        client.run("install . -pr=profile")
        assert "tool/1.1#platform - Platform" in client.out
        assert "DEPENDENCY tool/1.1" in client.out

    def test_consumer_resolved_revision(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                tool_requires = "tool/1.1"

                def generate(self):
                    for r, _ in self.dependencies.items():
                        self.output.info(f"DEPENDENCY {repr(r.ref)}")
                """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_tool_requires]\ntool/1.1#rev1"})
        client.run("install . -pr=profile")
        assert "tool/1.1 - Platform" in client.out
        assert "DEPENDENCY tool/1.1#rev1" in client.out

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
               tool_requires = "tool/1.1#rev1"

               def generate(self):
                   for r, _ in self.dependencies.items():
                       self.output.info(f"DEPENDENCY {repr(r.ref)}")
               """)
        client.save({"conanfile.py": conanfile})
        client.run("install . -pr=profile")
        assert "tool/1.1#rev1 - Platform" in client.out
        assert "DEPENDENCY tool/1.1#rev1" in client.out

    def test_consumer_unresolved_revision(self):
        """ if a recipe specifies an exact revision and so does the profiñe
        and it doesn't match, it is an error
        """
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                tool_requires = "tool/1.1#rev2"

                def generate(self):
                    for r, _ in self.dependencies.items():
                        self.output.info(f"DEPENDENCY {repr(r.ref)}")
                """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[platform_tool_requires]\ntool/1.1#rev1"})
        client.run("install . -pr=profile", assert_error=True)
        assert "ERROR: Package 'tool/1.1' not resolved" in client.out

    def test_require_build_context(self):
        """ https://github.com/conan-io/conan/issues/15659
        app -> libcurl --(tool-require)--> libtool -> automake -> autoconf
                                             \\--(br)-> automake -> autoconf
        """
        c = TestClient(light=True)
        c.save({"autoconf/conanfile.py": GenConanfile("autoconf", "0.1"),
                "automake/conanfile.py": GenConanfile("automake", "0.1").with_requires("autoconf/0.1"),
                "libtool/conanfile.py": GenConanfile("libtool", "0.1").with_requires("automake/0.1")
                                                                      .with_tool_requires("automake/0.1"),
                "libcurl/conanfile.py": GenConanfile("libcurl", "0.1").with_tool_requires("libtool/0.1"),
                "app/conanfile.py": GenConanfile().with_requires("libcurl/0.1"),
                "profile_build": "[settings]\nos=Linux\n[platform_tool_requires]\nautomake/0.1"})
        c.run("create autoconf")
        c.run("create automake")
        c.run("export libtool")
        c.run("export libcurl")
        c.run("install app -pr:b=profile_build --build=missing")
        assert "Install finished successfully" in c.out

    def test_platform_requires_error(self):
        """
        https://github.com/conan-io/conan/issues/19745
        """
        c = TestClient(light=True)
        profile = textwrap.dedent("""\
            include(default)

            [platform_tool_requires]
            cmake/[*]
            """)
        c.save({"conanfile.py": GenConanfile("catch2").with_tool_requires("cmake/[*]"),
                "profile": profile})

        c.run("create  --version=3.6.0 -pr=profile", assert_error=True)
        assert "AssertionError" not in c.out
        assert ("ERROR: Error reading 'profile' profile: Profile [platform_requires]/"
                "[platform_tool_requires] must be exact versions, "
                "not version ranges: [cmake/[*]]") in c.out


class TestToolRequiresLock:

    @pytest.mark.parametrize("revision", ["", "#myrev"])
    def test_system_tool_require_range(self, revision):
        c = TestClient(light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("tool/[>=1.0]"),
                "profile": f"[platform_tool_requires]\ntool/1.1{revision}"})
        c.run("lock create . -pr=profile")
        assert "tool/1.1 - Platform" in c.out
        lock = json.loads(c.load("conan.lock"))
        assert lock["build_requires"] == [f"tool/1.1{revision or '#platform'}"]

        c.run("install .", assert_error=True)
        assert "Package 'tool/1.1' not resolved: No remote defined" in c.out
        c.run("install . -pr=profile")
        assert f"tool/1.1{revision or '#platform'} - Platform" in c.out

        # even if we create a version within the range, it will error if not matching the profile
        c.save({"tool/conanfile.py": GenConanfile("tool", "1.1")})
        c.run("create tool")
        # if the profile points to another version it is an error, not in the lockfile
        c.save({"profile": f"[platform_tool_requires]\ntool/1.2{revision}"})
        c.run("install . -pr=profile", assert_error=True)
        assert f"ERROR: Requirement 'tool/1.2{revision or '#platform'}' not in lockfile" in c.out

        # if we relax the lockfile, we can still resolve to the platform_tool_requires
        # specified by the profile
        c.run("install . -pr=profile --lockfile-partial")
        assert f"tool/1.2{revision or '#platform'} - Platform" in c.out


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
                     "profile": "[platform_tool_requires]\ntool/1.1"})
        client.run("install . -pr=profile")
        assert "tool/1.1 - Platform" in client.out
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
        client = TestClient(light=True)
        client.save_home({"global.conf": f"core.package_id:default_build_mode={package_id_mode}"})
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("dep/1.0"),
                     "profile": "[platform_tool_requires]\ndep/1.0"})
        client.run("create . -pr=profile")
        assert "dep/1.0 - Platform" in client.out

    def test_package_id_explicit_revision(self):
        """
        Changing the system_tool_require revision affects consumers if package_revision_mode=recipe_revision
        """
        client = TestClient(light=True)
        client.save_home({"global.conf": "core.package_id:default_build_mode=recipe_revision_mode"})
        client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_tool_requires("dep/1.0"),
                     "profile": "[platform_tool_requires]\ndep/1.0#r1",
                     "profile2": "[platform_tool_requires]\ndep/1.0#r2"})
        client.run("create . -pr=profile")
        assert "dep/1.0#r1 - Platform" in client.out
        assert "pkg/1.0#27a56f09310cf1237629bae4104fe5bd:" \
               "ea0e320d94b4b70fcb3efbabf9ab871542f8f696 - Build" in client.out

        client.run("create . -pr=profile2")
        # pkg gets a new package_id because it is a different revision
        assert "dep/1.0#r2 - Platform" in client.out
        assert "pkg/1.0#27a56f09310cf1237629bae4104fe5bd:" \
               "334882884da082740e5a002a0b6fdb509a280159 - Build" in client.out
