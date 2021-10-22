import os
import platform
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load


# Without compiler, def rpath_flags(settings, os_build, lib_paths): doesn't append the -Wl...etc
def test_pkg_config_dirs():
    # https://github.com/conan-io/conan/issues/2756
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            name = "MyLib"
            version = "0.1"

            def package_info(self):
                self.cpp_info.frameworkdirs = []
                self.cpp_info.filter_empty = False
                libname = "mylib"
                fake_dir = os.path.join("/", "my_absoulte_path", "fake")
                include_dir = os.path.join(fake_dir, libname, "include")
                lib_dir = os.path.join(fake_dir, libname, "lib")
                lib_dir2 = os.path.join(self.package_folder, "lib2")
                self.cpp_info.includedirs = [include_dir]
                self.cpp_info.libdirs = [lib_dir, lib_dir2]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.run("install MyLib/0.1@ -g PkgConfigDeps")

    pc_path = os.path.join(client.current_folder, "MyLib.pc")
    assert os.path.exists(pc_path) is True
    pc_content = load(pc_path)
    expected_rpaths = ""
    if platform.system() in ("Linux", "Darwin"):
        expected_rpaths = ' -Wl,-rpath,"${libdir1}" -Wl,-rpath,"${libdir2}" '
    expected_content = textwrap.dedent("""\
        libdir1=/my_absoulte_path/fake/mylib/lib
        libdir2=${prefix}/lib2
        includedir1=/my_absoulte_path/fake/mylib/include

        Name: MyLib
        Description: Conan package: MyLib
        Version: 0.1
        Libs: -L"${libdir1}" -L"${libdir2}"%s
        Cflags: -I"${includedir1}\" """ % expected_rpaths)

    assert "\n".join(pc_content.splitlines()[1:]) == expected_content

    def assert_is_abs(path):
        assert os.path.isabs(path) is True

    for line in pc_content.splitlines():
        if line.startswith("includedir="):
            assert_is_abs(line[len("includedir="):])
            assert line.endswith("include") is True
        elif line.startswith("libdir="):
            assert_is_abs(line[len("libdir="):])
            assert line.endswith("lib") is True
        elif line.startswith("libdir3="):
            assert "${prefix}/lib2" in line


def test_empty_dirs():
    # Adding in package_info all the empty directories
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            name = "MyLib"
            version = "0.1"

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libdirs = []
                self.cpp_info.bindirs = []
                self.cpp_info.libs = []
                self.cpp_info.frameworkdirs = []
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.run("install MyLib/0.1@ -g PkgConfigDeps")

    pc_path = os.path.join(client.current_folder, "MyLib.pc")
    assert os.path.exists(pc_path) is True
    pc_content = load(pc_path)
    expected = textwrap.dedent("""
        Name: MyLib
        Description: Conan package: MyLib
        Version: 0.1
        Libs:%s
        Cflags: """ % " ")  # ugly hack for trailing whitespace removed by IDEs
    assert "\n".join(pc_content.splitlines()[1:]) == expected


def test_pkg_config_rpaths():
    # rpath flags are only generated for gcc and clang
    profile = textwrap.dedent("""\
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=7
        compiler.libcxx=libstdc++
        """)
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            name = "MyLib"
            version = "0.1"
            settings = "os", "compiler"
            exports = "mylib.so"

            def package(self):
                self.copy("mylib.so", dst="lib")

            def package_info(self):
                self.cpp_info.libs = ["mylib"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "linux_gcc": profile,
                 "mylib.so": "fake lib content"})
    client.run("create . -pr=linux_gcc")
    client.run("install MyLib/0.1@ -g PkgConfigDeps -pr=linux_gcc")

    pc_path = os.path.join(client.current_folder, "MyLib.pc")
    assert os.path.exists(pc_path) is True
    pc_content = load(pc_path)
    assert '-Wl,-rpath,"${libdir1}"' in pc_content


def test_system_libs():
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os

        class PkgConfigConan(ConanFile):
            name = "MyLib"
            version = "0.1"

            def package(self):
                save(os.path.join(self.package_folder, "lib", "file"), "")

            def package_info(self):
                self.cpp_info.libs = ["mylib1", "mylib2"]
                self.cpp_info.system_libs = ["system_lib1", "system_lib2"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.run("install MyLib/0.1@ -g PkgConfigDeps")

    pc_content = client.load("MyLib.pc")
    assert 'Libs: -L"${libdir1}" -lmylib1 -lmylib2 -lsystem_lib1 -lsystem_lib2 ' \
           '-Wl,-rpath,"${libdir1}" -F Frameworks' in pc_content


def test_multiple_include():
    # https://github.com/conan-io/conan/issues/7056
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os

        class PkgConfigConan(ConanFile):
            def package(self):
                for p in ["inc1", "inc2", "inc3/foo", "lib1", "lib2"]:
                    save(os.path.join(self.package_folder, p, "file"), "")

            def package_info(self):
                self.cpp_info.includedirs = ["inc1", "inc2", "inc3/foo"]
                self.cpp_info.libdirs = ["lib1", "lib2"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@")
    client.run("install pkg/0.1@ -g PkgConfigDeps")

    pc_content = client.load("pkg.pc")
    assert "includedir1=${prefix}/inc1" in pc_content
    assert "includedir2=${prefix}/inc2" in pc_content
    assert "includedir3=${prefix}/inc3/foo" in pc_content
    assert "libdir1=${prefix}/lib1" in pc_content
    assert "libdir2=${prefix}/lib2" in pc_content
    assert 'Libs: -L"${libdir1}" -L"${libdir2}"' in pc_content
    assert 'Cflags: -I"${includedir1}" -I"${includedir2}" -I"${includedir3}"' in pc_content


def test_custom_content():
    # https://github.com/conan-io/conan/issues/7661
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os
        import textwrap

        class PkgConfigConan(ConanFile):

            def package(self):
                save(os.path.join(self.package_folder, "include" ,"file"), "")
                save(os.path.join(self.package_folder, "lib" ,"file"), "")

            def package_info(self):
                custom_content = textwrap.dedent(\"""
                        datadir=${prefix}/share
                        schemasdir=${datadir}/mylib/schemas
                        bindir=${prefix}/bin
                    \""")
                self.cpp_info.set_property("pkg_config_custom_content", custom_content)
                self.cpp_info.includedirs = ["include"]
                self.cpp_info.libdirs = ["lib"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@")
    client.run("install pkg/0.1@ -g PkgConfigDeps")

    pc_content = client.load("pkg.pc")
    assert "libdir1=${prefix}/lib" in pc_content
    assert "datadir=${prefix}/share" in pc_content
    assert "schemasdir=${datadir}/mylib/schemas" in pc_content
    assert "bindir=${prefix}/bin" in pc_content
    assert "Name: pkg" in pc_content


def test_custom_content_components():
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os
        import textwrap

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.components["mycomponent"].set_property("pkg_config_custom_content",
                                                                     "componentdir=${prefix}/mydir")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@")
    client.run("install pkg/0.1@ -g PkgConfigDeps")
    pc_content = client.load("pkg-mycomponent.pc")
    assert "componentdir=${prefix}/mydir" in pc_content


def test_pkg_with_component_requires():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("other", "0.1").with_package_file("file.h", "0.1")})
    client.run("create . user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "other/0.1@user/channel"

            def package_info(self):
                self.cpp_info.components["mycomponent"].requires.append("other::other")
                self.cpp_info.components["myothercomp"].requires.append("mycomponent")

        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@")

    client2 = TestClient(cache_folder=client.cache_folder)
    conanfile = textwrap.dedent("""
        [requires]
        pkg/0.1

        [generators]
        PkgConfigDeps
        """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")
    pc_content = client2.load("pkg.pc")
    assert "Requires: pkg-mycomponent" in pc_content
    pc_content = client2.load("pkg-mycomponent.pc")
    assert "Requires: other" in pc_content
    pc_content = client2.load("pkg-myothercomp.pc")
    assert "Requires: pkg-mycomponent" in pc_content


def test_pkg_getting_public_requires():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["other_cmp1"]
                self.cpp_info.components["cmp2"].libs = ["other_cmp2"]
                self.cpp_info.components["cmp3"].requires.append("cmp1")

    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . other/1.0@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "other/1.0"

            def package_info(self):
                self.cpp_info.requires = ["other::cmp1"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@")

    client2 = TestClient(cache_folder=client.cache_folder)
    conanfile = textwrap.dedent("""
        [requires]
        pkg/0.1

        [generators]
        PkgConfigDeps
        """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")
    pc_content = client2.load("pkg.pc")
    assert "Requires: other-cmp1" in pc_content
    pc_content = client2.load("other.pc")
    assert "Requires: other-cmp1 other-cmp2 other-cmp3" in pc_content
    assert client2.load("other-cmp1.pc")
    assert client2.load("other-cmp2.pc")
    pc_content = client2.load("other-cmp3.pc")
    assert "Requires: other-cmp1" in pc_content
