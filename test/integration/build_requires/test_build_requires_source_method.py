import textwrap

import pytest

from conan.test.utils.tools import TestClient


class TestBuildEnvSource:
    @pytest.fixture()
    def client(self):
        c = TestClient()
        tool = textwrap.dedent(r"""
            import os
            from conan import ConanFile
            from conan.tools.files import chdir, save

            class Tool(ConanFile):
                name = "tool"
                version = "0.1"
                def package(self):
                    with chdir(self, self.package_folder):
                        echo = f"@echo off\necho MY-TOOL! {self.name}/{self.version}!!"
                        save(self, "bin/mytool.bat", echo)
                        save(self, "bin/mytool.sh", echo)
                        os.chmod("bin/mytool.sh", 0o777)
            """)
        c.save({"conanfile.py": tool})
        c.run("create .")
        return c

    def test_source_buildenv(self, client):
        c = client
        pkg = textwrap.dedent("""
            from conan import ConanFile
            import platform

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                tool_requires = "tool/0.1"

                source_buildenv = True

                def source(self):
                    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
                    self.run(cmd)
            """)
        c.save({"conanfile.py": pkg})
        c.run("create .")
        assert "MY-TOOL! tool/0.1" in c.out

        c.run("install .")  # to generate conanbuild script first, so it is available
        c.run("source .")
        assert "MY-TOOL! tool/0.1" in c.out

    def test_source_buildenv_layout(self, client):
        c = client
        pkg = textwrap.dedent("""
            from conan import ConanFile
            import platform

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                tool_requires = "tool/0.1"
                settings = "build_type"

                source_buildenv = True

                def layout(self):
                    self.folders.source = "mysrc"
                    bt = self.settings.get_safe("build_type") or "Release"
                    self.folders.generators = f"mybuild{bt}"

                def source(self):
                    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
                    self.run(cmd)
            """)
        c.save({"conanfile.py": pkg})
        c.run("create .")
        assert "MY-TOOL! tool/0.1" in c.out

        c.run("install .")  # to generate conanbuild script first, so it is available
        # But they are in a different folder, user can copy them to source folder to make
        # them available to source() method. This works
        # shutil.copytree(os.path.join(c.current_folder, "mybuild"),
        #                os.path.join(c.current_folder, "mysrc"))
        # Another possibility is user directly calling the "conanbuild" script to activate
        # The current solution defines "generators" to be robust for "conan source" command
        # defaulting to "Release" config
        c.run("source .")
        assert "MY-TOOL! tool/0.1" in c.out

    def test_source_buildenv_cmake_layout(self, client):
        c = client
        pkg = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout
            import platform

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                tool_requires = "tool/0.1"
                settings = "build_type"

                source_buildenv = True

                def layout(self):
                    cmake_layout(self)
                    bt = self.settings.get_safe("build_type") or "Release"
                    self.folders.generators = os.path.join(bt, "generators")

                def source(self):
                    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
                    self.run(cmd)
            """)
        c.save({"conanfile.py": pkg})
        c.run("create .")
        assert "MY-TOOL! tool/0.1" in c.out

        c.run("install .")
        c.run("source .")
        assert "MY-TOOL! tool/0.1" in c.out

    def test_source_buildenv_default_fail(self, client):
        c = client

        pkg = textwrap.dedent("""
            from conan import ConanFile
            import platform

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                tool_requires = "tool/0.1"

                def source(self):
                    cmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
                    self.run(cmd)
            """)
        c.save({"conanfile.py": pkg})
        c.run("create .", assert_error=True)
        assert "ERROR: pkg/0.1: Error in source() method, line 12" in c.out

        # Local will still work, because ``install`` generates env-scripts and no layout
        c.run("install .")
        c.run("source .")
        assert "MY-TOOL! tool/0.1" in c.out
