import textwrap

from conans.test.utils.tools import TestClient


def test_require_different_versions():
    """ this test demostrates that it is possible to tool_require different versions
    of the same thing, deactivating run=False (as long as their executables are not called the same)

    https://github.com/conan-io/conan/issues/13521
    """
    c = TestClient()
    gcc = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "gcc"
            def package(self):
                echo = f"@echo off\necho MYGCC={self.version}!!"
                save(self, os.path.join(self.package_folder, "bin", f"mygcc{self.version}.bat"), echo)
                save(self, os.path.join(self.package_folder, "bin", f"mygcc{self.version}.sh"), echo)
                os.chmod(os.path.join(self.package_folder, "bin", f"mygcc{self.version}.sh"), 0o777)
            """)
    wise = textwrap.dedent("""
        import os, platform
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "wise"
            version = "1.0"
            def build_requirements(self):
                self.tool_requires("gcc/1.0", run=False)
                self.tool_requires("gcc/2.0", run=False)

            def build(self):
                ext = "bat" if platform.system() == "Windows" else "sh"
                self.run(f"mygcc1.0.{ext}")
                self.run(f"mygcc2.0.{ext}")
            """)
    c.save({"gcc/conanfile.py": gcc,
            "wise/conanfile.py": wise})

    c.run("create gcc --version=1.0")
    c.run("create gcc --version=2.0")

    c.run("build wise")
    assert "gcc/1.0#3d6110b9e2b90074160fa33b6f0ea968 - Cache" in c.out
    assert "gcc/2.0#3d6110b9e2b90074160fa33b6f0ea968 - Cache" in c.out
    assert "MYGCC=1.0!!" in c.out
    assert "MYGCC=2.0!!" in c.out


def test_require_different_options():
    """ this test demostrates that it is possible to tool_require different options
    of the same thing, deactivating run=False (as long as their executables are not called the same)

    https://github.com/conan-io/conan/issues/13521
    """
    c = TestClient()
    gcc = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "gcc"
            version = "1.0"
            options = {"myoption": [1, 2]}
            def package(self):
                echo = f"@echo off\necho MYGCC={self.options.myoption}!!"
                save(self, os.path.join(self.package_folder, "bin", f"mygcc{self.options.myoption}.bat"), echo)
                save(self, os.path.join(self.package_folder, "bin", f"mygcc{self.options.myoption}.sh"), echo)
                os.chmod(os.path.join(self.package_folder, "bin", f"mygcc{self.options.myoption}.sh"), 0o777)
            """)
    wise = textwrap.dedent("""
        import os, platform
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "wise"
            version = "1.0"
            def build_requirements(self):
                self.tool_requires("gcc/1.0", run=False, options={"myoption": 1})
                self.tool_requires("gcc/1.0", run=False, options={"myoption": 2})

            def build(self):
                ext = "bat" if platform.system() == "Windows" else "sh"
                self.run(f"mygcc1.{ext}")
                self.run(f"mygcc2.{ext}")
            """)
    c.save({"gcc/conanfile.py": gcc,
            "wise/conanfile.py": wise})

    c.run("create gcc -o myoption=1")
    c.run("create gcc -o myoption=2")

    c.run("build wise")
    assert "gcc/1.0#616ce3babcecef39a27806c1a5f4b4ff - Cache" in c.out
    assert "MYGCC=1!!" in c.out
    assert "MYGCC=2!!" in c.out
