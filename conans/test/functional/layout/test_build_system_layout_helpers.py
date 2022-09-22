import os
import platform
import textwrap

import pytest
import six

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TurboTestClient
from conans.util.files import save, load


@pytest.fixture
def conanfile():
    conanfile = str(GenConanfile().with_import("from conans import tools")
                    .with_import("import os")
                    .with_setting("build_type").with_setting("arch")
                    .with_import("from conan.tools.layout import {ly}")
                    .with_import("from conan.tools.files import AutoPackager"))

    conanfile += """
    def source(self):
        tools.save("include/myheader.h", "")

    def build(self):
        tools.save("{libpath}/mylib.lib", "")

    def layout(self):
        {ly}(self)

    def package(self):
        AutoPackager(self).run()
    """
    return conanfile


subfolders_arch = {"armv7": "ARM", "armv8": "ARM64", "x86": None, "x86_64": "x64"}


@pytest.mark.parametrize("arch", ["x86_64", "x86", "armv7", "armv8"])
@pytest.mark.parametrize("build_type", ["Debug", "Release"])
def test_layout_in_cache(conanfile, build_type, arch):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
    requires. But by the default, the "package" is not followed
    """
    client = TurboTestClient()

    ref = ConanFileReference.loads("lib/1.0")
    libarch = subfolders_arch.get(arch)
    libpath = "{}{}".format(libarch + "/" if libarch else "", build_type)
    pref = client.create(ref, args="-s arch={} -s build_type={}".format(arch, build_type),
                         conanfile=conanfile.format(ly="vs_layout", libpath=libpath))
    bf = client.cache.package_layout(pref.ref).build(pref)
    pf = client.cache.package_layout(pref.ref).package(pref)

    # Check the build folder
    assert os.path.exists(os.path.join(os.path.join(bf, libpath), "mylib.lib"))

    # Check the package folder
    assert os.path.exists(os.path.join(pf, "lib/mylib.lib"))
    assert os.path.exists(os.path.join(pf, "include", "myheader.h"))


@pytest.mark.parametrize("arch", ["x86_64", "x86", "armv7", "armv8"])
@pytest.mark.parametrize("build_type", ["Debug", "Release"])
def test_layout_with_local_methods(conanfile, build_type, arch):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
        requires. But by the default, the "package" is not followed
        """
    client = TestClient()
    libarch = subfolders_arch.get(arch)
    libpath = "{}{}".format(libarch + "/" if libarch else "", build_type)
    client.save({"conanfile.py": conanfile.format(ly="vs_layout", libpath=libpath)})
    client.run("install . lib/1.0@ -s build_type={} -s arch={}".format(build_type, arch))
    client.run("source .")
    # Check the source folder (release)
    assert os.path.exists(os.path.join(client.current_folder, "include", "myheader.h"))
    client.run("build .")
    # Check the build folder (release)
    assert os.path.exists(os.path.join(os.path.join(client.current_folder, libpath), "mylib.lib"))

    # Check the package
    client.run("package .", assert_error=True)
    assert "The usage of the 'conan package' local method is disabled when using layout()" \
           "" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Removing msvc compiler")
def test_error_no_msvc():
    # https://github.com/conan-io/conan/issues/9953
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import cmake_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def layout(self):
                cmake_layout(self)
        """)
    settings_yml = textwrap.dedent("""
        os: [Windows]
        os_build: [Windows]
        arch_build: [x86_64]
        compiler:
            gcc:
                version: ["8"]
        build_type: [Release]
        arch: [x86_64]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    save(client.cache.settings_path, settings_yml)
    client.run('install . -s os=Windows -s build_type=Release -s arch=x86_64 '
               '-s compiler=gcc -s compiler.version=8')
    assert "Installing" in client.out


def test_error_no_build_type():
    # https://github.com/conan-io/conan/issues/9953
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import cmake_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch"
            def layout(self):
                cmake_layout(self)
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run('install .',  assert_error=True)
    assert " 'build_type' setting not defined, it is necessary for cmake_layout()" in client.out


@pytest.mark.skipif(six.PY2, reason="only Py3")
def test_cmake_layout_external_sources():
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import cmake_layout
        from conan.tools.files import save, copy, load
        class Pkg(ConanFile):
            settings = "os", "build_type"
            exports_sources = "exported.txt"

            def layout(self):
                cmake_layout(self, src_folder="src")

            def generate(self):
                save(self, "generate.txt", "generate")

            def source(self):
                save(self, "source.txt", "foo")

            def build(self):
                c1 = load(self, os.path.join(self.source_folder, "source.txt"))
                c2 = load(self, os.path.join(self.source_folder, "..", "exported.txt"))
                save(self, "build.txt", c1 + c2)

            def package(self):
                copy(self, "build.txt", self.build_folder, os.path.join(self.package_folder, "res"))
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile, "exported.txt": "exported_contents"})
    client.run("create . foo/1.0@ -s os=Linux")
    assert "Packaged 1 '.txt' file: build.txt" in client.out

    # Local flow
    client.run("install . foo/1.0 -s os=Linux")
    assert os.path.exists(os.path.join(client.current_folder, "build", "generators", "generate.txt"))
    client.run("source .")
    assert os.path.exists(os.path.join(client.current_folder, "src", "source.txt"))
    client.run("build .")
    contents = load(os.path.join(client.current_folder, "build", "Release", "build.txt"))
    assert contents == "fooexported_contents"
    client.run("export-pkg . foo/1.0@ --force")
    assert "Packaged 1 '.txt' file: build.txt" in client.out


@pytest.mark.skipif(six.PY2, reason="only Py3")
@pytest.mark.parametrize("with_build_type", [True, False])
def test_basic_layout_external_sources(with_build_type):
    conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conan.tools.layout import basic_layout
            from conan.tools.files import save, load, copy
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch"{}
                exports_sources = "exported.txt"

                def layout(self):
                    basic_layout(self, src_folder="src")

                def generate(self):
                    save(self, "generate.txt", "generate")

                def source(self):
                    save(self, "source.txt", "foo")

                def build(self):
                    c1 = load(self, os.path.join(self.source_folder, "source.txt"))
                    c2 = load(self, os.path.join(self.source_folder, "..", "exported.txt"))
                    save(self, "build.txt", c1 + c2)

                def package(self):
                    copy(self, "build.txt", self.build_folder, os.path.join(self.package_folder, "res"))
            """)
    if with_build_type:
        conanfile = conanfile.format(', "build_type"')
    else:
        conanfile = conanfile.format("")
    client = TestClient()
    client.save({"conanfile.py": conanfile, "exported.txt": "exported_contents"})
    client.run("create . foo/1.0@ -s os=Linux")
    assert "Packaged 1 '.txt' file: build.txt" in client.out

    # Local flow
    build_folder = "build-release" if with_build_type else "build"
    client.run("install . foo/1.0 -s os=Linux")
    assert os.path.exists(os.path.join(client.current_folder, build_folder, "conan", "generate.txt"))
    client.run("source .")
    assert os.path.exists(os.path.join(client.current_folder, "src", "source.txt"))
    client.run("build .")
    contents = load(os.path.join(client.current_folder, build_folder, "build.txt"))
    assert contents == "fooexported_contents"
    client.run("export-pkg . foo/1.0@ --force")
    assert "Packaged 1 '.txt' file: build.txt" in client.out


@pytest.mark.skipif(six.PY2, reason="only Py3")
@pytest.mark.parametrize("with_build_type", [True, False])
def test_basic_layout_no_external_sources(with_build_type):
    conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conan.tools.layout import basic_layout
            from conan.tools.files import save, load, copy
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch"{}
                exports_sources = "exported.txt"

                def layout(self):
                    basic_layout(self)

                def generate(self):
                    save(self, "generate.txt", "generate")

                def build(self):
                    contents = load(self, os.path.join(self.source_folder, "exported.txt"))
                    save(self, "build.txt", contents)

                def package(self):
                    copy(self, "build.txt", self.build_folder, os.path.join(self.package_folder,
                                                                            "res"))
            """)
    if with_build_type:
        conanfile = conanfile.format(', "build_type"')
    else:
        conanfile = conanfile.format("")

    client = TestClient()
    client.save({"conanfile.py": conanfile, "exported.txt": "exported_contents"})
    client.run("create . foo/1.0@ -s os=Linux")
    assert "Packaged 1 '.txt' file: build.txt" in client.out

    # Local flow
    client.run("install . foo/1.0 -s os=Linux")

    build_folder = "build-release" if with_build_type else "build"
    assert os.path.exists(os.path.join(client.current_folder, build_folder, "conan", "generate.txt"))

    client.run("build .")
    contents = load(os.path.join(client.current_folder, build_folder, "build.txt"))
    assert contents == "exported_contents"
    client.run("export-pkg . foo/1.0@ --force")
    assert "Packaged 1 '.txt' file: build.txt" in client.out


def test_cmake_layout_custom_build_folder():
    # https://github.com/conan-io/conan/issues/11838
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        class Pkg(ConanFile):
            settings = "os", "build_type"
            generators = "CMakeToolchain"
            def layout(self):
                cmake_layout(self, src_folder="src", build_folder="mybuild")
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert os.path.exists(os.path.join(client.current_folder,
                                       "mybuild/generators/conan_toolchain.cmake"))
