import textwrap

from conan.test.utils.tools import TestClient


class TestSystemReqs:
    base_conanfile = textwrap.dedent("""\
        from conan import ConanFile

        class TestSystemReqs(ConanFile):
            name = "test"
            version = "0.1"

            def system_requirements(self):
                self.output.info("*+Running system requirements+*")
        """)

    def test_force_system_reqs_rerun(self):
        client = TestClient(light=True)
        client.save({'conanfile.py': self.base_conanfile})
        client.run("create . ")
        assert "*+Running system requirements+*" in client.out
        client.run("install --requires=test/0.1")
        assert "*+Running system requirements+*" in client.out

    def test_local_system_requirements(self):
        client = TestClient(light=True)
        client.save({'conanfile.py': self.base_conanfile})
        client.run("install .")
        assert "*+Running system requirements+*" in client.out


class TestBuildSystemRequirements:

    def test_called_when_building_from_source(self):
        """build_system_requirements is called when the package binary is built from source."""
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def system_requirements(self):
                    self.output.info("*+system_requirements called+*")
                def build_system_requirements(self):
                    self.output.info("*+build_system_requirements called+*")
        """)
        c.save({"conanfile.py": conanfile})
        c.run("create .")
        assert "*+system_requirements called+*" in c.out
        assert "*+build_system_requirements called+*" in c.out

        # Already in cache
        c.run("install --requires=pkg/0.1")
        assert "*+system_requirements called+*" in c.out
        assert "*+build_system_requirements called+*" not in c.out  # NOT CALLED!

        c.run("install --requires=pkg/0.1 --build=pkg*")
        assert "*+system_requirements called+*" in c.out
        assert "*+build_system_requirements called+*" in c.out  # CALLED!

    def test_local_conanfile_build_system_requirements(self):
        """build_system_requirements is called for the root conanfile during conan install ."""
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def build_system_requirements(self):
                    self.output.info("*+build_system_requirements called+*")
        """)
        c.save({"conanfile.py": conanfile})
        c.run("install .")
        assert "*+build_system_requirements called+*" in c.out


class TestBuildSystemRequirementsArch:
    """Integration tests verifying that _SystemPackageManagerTool uses settings_build.arch
    when called from build_system_requirements() and settings.arch in system_requirements().

    The conanfile overrides run() to capture the package manager command without executing it.
    Cross-compilation is simulated with -s:h arch=armv8 -s:b arch=x86_64.
    """

    # Shared conf flags used in every test run
    _cross_args = ("-s:b os=Linux -s:b arch=x86_64 "
                   "-s:h os=Linux -s:h arch=armv8 "
                   "-c tools.system.package_manager:tool=apt-get "
                   "-c tools.system.package_manager:mode=install")

    def test_both_methods_correct_arch(self):
        """When both methods are defined on the same recipe:
        - build_system_requirements() installs build tools without cross-arch suffix
        - system_requirements() installs host libraries WITH cross-arch suffix
        """
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.system.package_manager import Apt

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "arch"

                def run(self, command, *args, **kwargs):
                    self.output.info(f"CAPTURED: {command}")
                    return 0

                def system_requirements(self):
                    Apt(self).install(["libopencv-dev"], check=False)

                def build_system_requirements(self):
                    Apt(self).install(["cmake"], check=False)
        """)
        c.save({"conanfile.py": conanfile})
        c.run(f"create . {self._cross_args}")
        # Build tool: no arch suffix
        assert "CAPTURED: apt-get install -y --no-install-recommends cmake" in c.out
        # Host library: arm64 suffix present
        assert "CAPTURED: apt-get install -y --no-install-recommends libopencv-dev:arm64" in c.out
