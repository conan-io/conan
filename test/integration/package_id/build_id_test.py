import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

conanfile = """import os
from conan import ConanFile

class MyTest(ConanFile):
    name = "pkg"
    version = "0.1"
    settings = "os", "build_type"
    build_policy = "missing"

    def build_id(self):
        if self.settings.os == "Windows":
            self.info_build.settings.build_type = "Any"

    def build(self):
        self.output.info("Building my code!")

    def package(self):
        self.output.info("Packaging %s!" % self.settings.build_type)
"""


class TestBuildIdTest:

    def test_create(self):
        # Ensure that build_id() works when multiple create calls are made
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create .  -s os=Windows -s build_type=Release")
        assert "pkg/0.1: Calling build()" in client.out
        assert "Building my code!" in client.out
        assert "Packaging Release!" in client.out
        # Debug must not build
        client.run("create .  -s os=Windows -s build_type=Debug")
        assert "pkg/0.1: Calling build()" not in client.out
        assert "Building my code!" not in client.out
        assert "Packaging Debug!" in client.out

        client.run("create . -s os=Linux -s build_type=Release")
        assert "pkg/0.1: Calling build()" in client.out
        assert "Building my code!" in client.out
        assert "Packaging Release!" in client.out
        client.run("create .  -s os=Linux -s build_type=Debug")
        assert "Building my code!" in client.out
        assert "pkg/0.1: Calling build()" in client.out
        assert "Packaging Debug!" in client.out

    def test_basic_install(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . ")
        # Windows Debug
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Debug')
        assert "Building my code!" in client.out
        assert "Packaging Debug!" in client.out

        # Package Windows Release, it will reuse the previous build
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Release')
        assert "Building my code!" not in client.out
        assert "Packaging Release!" in client.out

        # Now Linux Debug
        client.run('install --requires=pkg/0.1 -s os=Linux -s build_type=Debug')
        assert "Building my code!" in client.out
        assert "Packaging Debug!" in client.out

        # Linux Release must build again, as it is not affected by build_id()
        client.run('install --requires=pkg/0.1 -s os=Linux -s build_type=Release')
        assert "Building my code!" in client.out
        assert "Packaging Release!" in client.out

        # But if the packages are removed, and we change the order, keeps working
        client.run("remove *:* -c")
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Release')
        assert "Building my code!" in client.out
        assert "Packaging Release!" in client.out

        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Debug')
        assert "Building my code!" not in client.out
        assert "Packaging Debug!" in client.out

    def test_clean_build(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . ")
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Debug')
        # Package Windows Release, it will reuse the previous build
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Release')
        assert "Building my code!" not in client.out
        assert "Packaging Release!" in client.out

        client.run("cache clean")  # packages are still there
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Debug')
        assert "Building my code!" not in client.out
        assert "Packaging Release!" not in client.out
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Release')
        assert "Building my code!" not in client.out
        assert "Packaging Release!" not in client.out

        # Lets force the first rebuild, different order Linux first
        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Release --build=pkg*')
        assert "Building my code!" in client.out
        assert "Packaging Release!" in client.out

        client.run('install --requires=pkg/0.1 -s os=Windows -s build_type=Debug --build=pkg*')
        assert "Building my code!" not in client.out
        assert "Packaging Debug!" in client.out

    def test_failed_build(self):
        # Repeated failed builds keep failing
        fail_conanfile = textwrap.dedent("""\
            from conan import ConanFile
            class MyTest(ConanFile):
                settings = "build_type"
                def build(self):
                    raise Exception("Failed build!!")
            """)
        client = TestClient()
        # NORMAL case, every create fails
        client.save({"conanfile.py": fail_conanfile})
        client.run("create . --name=pkg --version=0.1 ", assert_error=True)
        assert "ERROR: pkg/0.1: Error in build() method, line 5" in client.out
        client.run("create . --name=pkg --version=0.1 ", assert_error=True)
        assert "ERROR: pkg/0.1: Error in build() method, line 5" in client.out
        # now test with build_id
        client.save({"conanfile.py": fail_conanfile +
                     "    def build_id(self): self.info_build.settings.build_type = 'any'"})
        client.run("create . --name=pkg --version=0.1 ", assert_error=True)
        assert "ERROR: pkg/0.1: Error in build() method, line 5" in client.out
        client.run("create . --name=pkg --version=0.1 ", assert_error=True)
        assert "ERROR: pkg/0.1: Error in build() method, line 5" in client.out

    def test_any_os_arch(self):
        conanfile_os = textwrap.dedent("""
            import os
            from conan import ConanFile

            class MyTest(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "arch", "build_type", "compiler"

                def build_id(self):
                    self.info_build.settings.build_type = "AnyValue"
                    self.info_build.settings.os = "AnyValue"
                    self.info_build.settings.arch = "AnyValue"
                    self.info_build.settings.compiler = "AnyValue"

                def build(self):
                    self.output.info("Building my code!")

                def package(self):
                    self.output.info("Packaging %s-%s!" % (self.settings.os, self.settings.arch))
            """)

        client = TestClient()
        client.save({"conanfile.py": conanfile_os})
        client.run("create .  -s os=Windows -s arch=x86_64 -s build_type=Release")
        assert "pkg/0.1: Calling build()" in client.out
        assert "Building my code!" in client.out
        assert "Packaging Windows-x86_64!" in client.out
        # Others must not build
        client.run("create .  -s os=Linux -s arch=x86 -s build_type=Debug")
        assert "pkg/0.1: Calling build()" not in client.out
        assert "Building my code!" not in client.out
        assert "Packaging Linux-x86!" in client.out


def test_remove_require():
    c = TestClient()
    remove = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "consumer"
            version = "1.0"
            requires = "dep/1.0"
            def build_id(self):
                self.info_build.requires.remove("dep")
        """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "consumer/conanfile.py": remove})
    c.run("create dep")
    c.run("create consumer")


def test_build_id_error():
    """
    https://github.com/conan-io/conan/issues/14537
    This was failing because the ``DB get_matching_build_id()`` function was returning all prefs
    for a given ref, and the order could be by alphabetic package_id, but only the first one really
    contains the build folder with the artifacts. It was fixed by defining the DB "build_id" only
    for the first reference containing that build_id, not all
    """
    c = TestClient()
    myconan = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Version

        class BuildIdTestConan(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "arch", "compiler", "build_type"
            options = {"shared": [True, False]}
            default_options = {"shared": False}

            def build_id(self):
                self.info_build.settings.build_type = "Any"
                self.info_build.options.shared = "Any"

            def package_id(self):
                compilerVer = Version(str(self.info.settings.compiler.version))
                if self.info.settings.compiler == "gcc":
                    if compilerVer >= "7":
                        self.info.settings.compiler.version = "7+"
    """)
    host_profile = textwrap.dedent("""
        [settings]
        arch = x86_64
        build_type = Release
        compiler = gcc
        compiler.cppstd = gnu17
        compiler.libcxx = libstdc++11
        compiler.version = 8
        os = Linux
    """)

    c.save({"conanfile.py": myconan,
            "myprofile": host_profile})
    c.run("create . "
          "-pr:h myprofile -pr:b myprofile "
          "-s build_type=Debug -o pkg/*:shared=True")
    c.assert_listed_binary({"pkg/0.1": ("538f60f3919ea9b8ea9e7c63c5948abe44913bec", "Build")})
    assert "pkg/0.1: build_id() computed 7d169d0d018d239cff27eb081e3f6575554e05c5" in c.out
    c.run("create . "
          "-pr:h myprofile -pr:b myprofile "
          "-s build_type=Debug -o pkg/*:shared=False")
    c.assert_listed_binary({"pkg/0.1": ("ba41c80b0373ef66e2ca95ed56961153082fbcd9", "Build")})
    assert "pkg/0.1: build_id() computed 7d169d0d018d239cff27eb081e3f6575554e05c5" in c.out
    assert "pkg/0.1: Won't be built, using previous build folder as defined in build_id()" in c.out
    c.run("create . "
          "-pr:h myprofile -pr:b myprofile "
          "-s build_type=Release -o pkg/*:shared=True")
    c.assert_listed_binary({"pkg/0.1": ("2eb252449df37d245568e32e5a41d0540db3c6e2", "Build")})
    assert "pkg/0.1: build_id() computed 7d169d0d018d239cff27eb081e3f6575554e05c5" in c.out
    assert "pkg/0.1: Won't be built, using previous build folder as defined in build_id()" in c.out
    c.run("create . "
          "-pr:h myprofile -pr:b myprofile "
          "-s build_type=Release -o pkg/*:shared=False")
    c.assert_listed_binary({"pkg/0.1": ("978c5442906f96846ccb201129ba1559071ce4ab", "Build")})
    assert "pkg/0.1: build_id() computed 7d169d0d018d239cff27eb081e3f6575554e05c5" in c.out
    assert "pkg/0.1: Won't be built, using previous build folder as defined in build_id()" in c.out
