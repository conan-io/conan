import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


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
    wine = textwrap.dedent("""
        import os, platform
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "wine"
            version = "1.0"
            def build_requirements(self):
                self.tool_requires("gcc/1.0", run=False)
                self.tool_requires("gcc/2.0", run=False)

            def generate(self):
                gcc1 = self.dependencies.build["gcc/1.0"]
                assert gcc1.ref.version == "1.0"
                gcc2 = self.dependencies.build["gcc/2.0"]
                assert gcc2.ref.version == "2.0"

            def build(self):
                ext = "bat" if platform.system() == "Windows" else "sh"
                self.run(f"mygcc1.0.{ext}")
                self.run(f"mygcc2.0.{ext}")
            """)
    c.save({"gcc/conanfile.py": gcc,
            "wine/conanfile.py": wine})

    c.run("create gcc --version=1.0")
    c.run("create gcc --version=2.0")

    c.run("build wine --lockfile-out=conan.lock")
    assert "gcc/1.0#3d6110b9e2b90074160fa33b6f0ea968 - Cache" in c.out
    assert "gcc/2.0#3d6110b9e2b90074160fa33b6f0ea968 - Cache" in c.out
    assert "MYGCC=1.0!!" in c.out
    assert "MYGCC=2.0!!" in c.out
    lock = c.load("wine/conan.lock")
    assert "gcc/1.0#3d6110b9e2b90074160fa33b6f0ea968" in lock
    assert "gcc/2.0#3d6110b9e2b90074160fa33b6f0ea968" in lock


def test_require_different_versions_profile_override():
    """ same as above but what if the profile is the one overriding the version?
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
    wine = textwrap.dedent("""
        import os, platform
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "wine"
            version = "1.0"
            def build_requirements(self):
                self.tool_requires("gcc/1.0", run=False)

            def build(self):
                ext = "bat" if platform.system() == "Windows" else "sh"
                self.run(f"mygcc1.0.{ext}")
                self.run(f"mygcc2.0.{ext}")
            """)
    c.save({"gcc/conanfile.py": gcc,
            "wine/conanfile.py": wine,
            "profile": "[tool_requires]\ngcc/2.0"})

    c.run("create gcc --version=1.0")
    c.run("create gcc --version=2.0")

    c.run("build wine -pr=profile --lockfile-out=conan.lock")
    assert "gcc/1.0#3d6110b9e2b90074160fa33b6f0ea968 - Cache" in c.out
    assert "gcc/2.0#3d6110b9e2b90074160fa33b6f0ea968 - Cache" in c.out
    assert "MYGCC=1.0!!" in c.out
    assert "MYGCC=2.0!!" in c.out
    lock = c.load("wine/conan.lock")
    assert "gcc/1.0#3d6110b9e2b90074160fa33b6f0ea968" in lock
    assert "gcc/2.0#3d6110b9e2b90074160fa33b6f0ea968" in lock


def test_require_different_versions_profile_override_build_script():
    """ build-scripts by default do the right thing, because they have run=True
    (they could be runnable shell scripts)
    """
    c = TestClient(light=True)
    buildscripts = GenConanfile("buildscripts").with_package_type("build-scripts")
    wine = GenConanfile("wine", "1.0").with_tool_requirement("buildscripts/1.0")
    c.save({"buildscripts/conanfile.py": buildscripts,
            "wine/conanfile.py": wine,
            "profile": "[tool_requires]\nbuildscripts/2.0"})

    c.run("create buildscripts --version=2.0")

    c.run("build wine -pr=profile --lockfile-out=conan.lock")
    assert "buildscripts/1.0" not in c.out
    assert "buildscripts/2.0#fced952ee7aba96f858b70c7d6c9c8d2 - Cache" in c.out
    lock = c.load("wine/conan.lock")
    assert "buildscripts/1.0" not in lock
    assert "buildscripts/2.0#fced952ee7aba96f858b70c7d6c9c8d2" in lock


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
    wine = textwrap.dedent("""
        import os, platform
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "wine"
            version = "1.0"
            def build_requirements(self):
                self.tool_requires("gcc/1.0", run=False, options={"myoption": 1})
                self.tool_requires("gcc/1.0", run=False, options={"myoption": 2})

            def generate(self):
                gcc1 = self.dependencies.build.get("gcc", options={"myoption": 1})
                assert gcc1.options.myoption == "1"
                gcc2 = self.dependencies.build.get("gcc", options={"myoption": 2})
                assert gcc2.options.myoption == "2"

            def build(self):
                ext = "bat" if platform.system() == "Windows" else "sh"
                self.run(f"mygcc1.{ext}")
                self.run(f"mygcc2.{ext}")
            """)
    c.save({"gcc/conanfile.py": gcc,
            "wine/conanfile.py": wine})

    c.run("create gcc -o myoption=1")
    c.run("create gcc -o myoption=2")

    c.run("build wine --lockfile-out=conan.lock")
    assert "gcc/1.0#616ce3babcecef39a27806c1a5f4b4ff - Cache" in c.out
    assert "MYGCC=1!!" in c.out
    assert "MYGCC=2!!" in c.out
    lock = c.load("wine/conan.lock")
    # Testing it doesn't crash or anything like that
    assert "gcc/1.0#616ce3babcecef39a27806c1a5f4b4ff" in lock


def test_require_different_versions_transitive():
    """
    https://github.com/conan-io/conan/issues/18086
    """
    c = TestClient(default_server_user=True)
    qemu = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "myqemu"
            package_type = "application"
            def package(self):
                echo = f"@echo off\necho RUNNING {self.name}/{self.version}!!"
                save(self, os.path.join(self.package_folder, "bin", f"{self.name}.bat"), echo)
                save(self, os.path.join(self.package_folder, "bin", f"{self.name}.sh"), echo)
                os.chmod(os.path.join(self.package_folder, "bin", f"{self.name}.sh"), 0o777)
            """)
    snippy = textwrap.dedent(r"""
        import os, platform
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "snippy"
            version = "1.0"
            build_policy = "missing"
            upload_policy = "skip"
            package_type = "application"
            def requirements(self):
                self.requires("myqemu/1.0", visible=False)
            def finalize(self):
                pf = self.dependencies["myqemu"].cpp_info.bindir.replace("\\", "/")
                c = f'call "{pf}/myqemu.bat"' if platform.system() == "Windows" else f'"{pf}/myqemu.sh"'
                echo = f"@echo off\necho RUNNING {self.name}/{self.version}!!\n{c}"
                save(self, os.path.join(self.package_folder, "bin", f"{self.name}.bat"), echo)
                save(self, os.path.join(self.package_folder, "bin", f"{self.name}"), echo)
                os.chmod(os.path.join(self.package_folder, "bin", f"{self.name}"), 0o777)
            """)
    valgrind = textwrap.dedent(r"""
        import os, platform
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "valgrind"
            version = "1.0"
            build_policy = "missing"
            upload_policy = "skip"
            package_type = "application"
            def requirements(self):
                self.requires("myqemu/2.0", visible=False)
            def finalize(self):
                pf = self.dependencies["myqemu"].cpp_info.bindir.replace("\\", "/")
                c = f'call "{pf}/myqemu.bat"' if platform.system() == "Windows" else f'"{pf}/myqemu.sh"'
                echo = f"@echo off\necho RUNNING {self.name}/{self.version}!!\n{c}"
                save(self, os.path.join(self.package_folder, "bin", f"{self.name}.bat"), echo)
                save(self, os.path.join(self.package_folder, "bin", f"{self.name}"), echo)
                os.chmod(os.path.join(self.package_folder, "bin", f"{self.name}"), 0o777)
            """)
    consumer = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            def build_requirements(self):
                self.tool_requires("snippy/1.0")
                self.tool_requires("valgrind/1.0")
            def build(self):
                self.run("valgrind")
                self.run("snippy")
        """)

    c.save({"qemu/conanfile.py": qemu,
            "snippy/conanfile.py": snippy,
            "valgrind/conanfile.py": valgrind,
            "consumer/conanfile.py": consumer})

    c.run("create qemu --version=1.0")
    c.run("create qemu --version=2.0")
    c.run("create snippy")
    c.run("create valgrind")
    c.run("build consumer")
    assert "RUNNING valgrind/1.0!!" in c.out
    assert "RUNNING myqemu/2.0!!" in c.out
    assert "RUNNING snippy/1.0!!" in c.out
    assert "RUNNING myqemu/1.0!!" in c.out

    c.run("upload * -r=default -c")
    c.run("remove * -c")
    # Re-downloads and it works
    c.run("build consumer")
    assert "RUNNING valgrind/1.0!!" in c.out
    assert "RUNNING myqemu/2.0!!" in c.out
    assert "RUNNING snippy/1.0!!" in c.out
    assert "RUNNING myqemu/1.0!!" in c.out
