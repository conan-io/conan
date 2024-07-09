import platform
import pytest
import os
import textwrap
import pathlib

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.tools.gnu.makedeps import CONAN_MAKEFILE_FILENAME


def test_make_dirs_with_abs_path():
    """
    MakeDeps should support absolute paths when cppinfp
    """
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile

        class TestMakeDirsConan(ConanFile):
            name = "mylib"
            version = "0.1"

            def package_info(self):
                self.cpp_info.frameworkdirs = []
                libname = "mylib"
                fake_dir = os.path.join("/", "my_absoulte_path", "fake")
                include_dir = os.path.join(fake_dir, libname, "include")
                lib_dir = os.path.join(fake_dir, libname, "lib")
                lib_dir2 = os.path.join(self.package_folder, "lib2")
                self.cpp_info.includedirs = [include_dir]
                self.cpp_info.libdirs = [lib_dir, lib_dir2]
                self.cpp_info.set_property("my_prop", "my prop value")
                self.cpp_info.set_property("my_prop_with_newline", "my\\nprop")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.run("install --requires=mylib/0.1@ -g MakeDeps")

    makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
    print(makefile_content)
    prefix = pathlib.Path(client.current_folder).drive if platform.system() == "Windows" else ""
    assert 'CONAN_NAME_MYLIB = mylib' in makefile_content
    assert 'CONAN_VERSION_MYLIB = 0.1' in makefile_content
    assert f'CONAN_LIB_DIRS_MYLIB = \\\n\t$(CONAN_LIB_DIR_FLAG){prefix}/my_absoulte_path/fake/mylib/lib \\\n\t$(CONAN_LIB_DIR_FLAG)$(CONAN_ROOT_MYLIB)/lib2' in makefile_content
    assert f'CONAN_INCLUDE_DIRS_MYLIB = $(CONAN_INCLUDE_DIR_FLAG){prefix}/my_absoulte_path/fake/mylib/include' in makefile_content
    assert 'CONAN_BIN_DIRS_MYLIB = $(CONAN_BIN_DIR_FLAG)$(CONAN_ROOT_MYLIB)/bin' in makefile_content
    assert 'CONAN_PROPERTY_MYLIB_MY_PROP = my prop value' in makefile_content
    assert 'CONAN_PROPERTY_MYLIB_MY_PROP_WITH_NEWLINE' not in makefile_content
    assert "WARN: Skipping propery 'my_prop_with_newline' because it contains newline" in client.stderr

    lines = makefile_content.splitlines()
    for line_no, line in enumerate(lines):
        includedir_pattern = "CONAN_INCLUDE_DIRS_MYLIB = $(CONAN_INCLUDE_DIRS_FLAG)"
        if line.startswith(includedir_pattern):
            assert os.path.isabs(line[len(includedir_pattern):])
            assert line.endswith("include")
        elif line.startswith("\t$(CONAN_LIB_DIRS_FLAG)") and 'my_absoulte_path' in line:
            assert os.path.isabs(line[len("\t$(CONAN_LIB_DIRS_FLAG)"):-2])
            assert line.endswith("lib \\")
        elif line.startswith("\t$(CONAN_LIB_DIRS_FLAG)") and line.endswith('lib2'):
            assert "\t$(CONAN_LIB_DIRS_FLAG)$(CONAN_ROOT_MYLIB)/lib2" in line


def test_make_empty_dirs():
    """
    MakeDeps should support cppinfo empty dirs
    """
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile

        class TestMakeDepsConan(ConanFile):
            name = "mylib"
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
    client.run("install --requires=mylib/0.1@ -g MakeDeps")

    makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
    assert 'CONAN_ROOT_MYLIB' in makefile_content
    assert 'SYSROOT' not in makefile_content
    assert 'CONAN_INCLUDE_DIRS' not in makefile_content
    assert 'CONAN_LIB_DIRS' not in makefile_content
    assert 'CONAN_BIN_DIRS' not in makefile_content
    assert 'CONAN_LIBS' not in makefile_content
    assert 'CONAN_FRAMEWORK_DIRS' not in makefile_content
    assert 'CONAN_PROPERTY' not in makefile_content


def test_libs_and_system_libs():
    """
    MakeDeps should support cppinfo system_libs with regular libs
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os

        class TestMakeDepsConan(ConanFile):
            name = "mylib"
            version = "0.1"

            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "file"), "")

            def package_info(self):
                self.cpp_info.libs = ["mylib1", "mylib2"]
                self.cpp_info.system_libs = ["system_lib1", "system_lib2"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.run("install --requires=mylib/0.1@ -g MakeDeps")

    makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
    assert "CONAN_LIBS_MYLIB = \\\n\t$(CONAN_LIB_FLAG)mylib1 \\\n\t$(CONAN_LIB_FLAG)mylib2" in makefile_content
    assert "CONAN_SYSTEM_LIBS_MYLIB = \\\n\t$(CONAN_SYSTEM_LIB_FLAG)system_lib1 \\\n\t$(CONAN_SYSTEM_LIB_FLAG)system_lib2" in makefile_content
    assert "CONAN_LIBS = $(CONAN_LIBS_MYLIB)" in makefile_content
    assert "CONAN_SYSTEM_LIBS = $(CONAN_SYSTEM_LIBS_MYLIB)" in makefile_content


def test_multiple_include_and_lib_dirs():
    """
    MakeDeps should support cppinfo multiple include directories
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os

        class TestMakeDepsConan(ConanFile):
            def package(self):
                for p in ["inc1", "inc2", "inc3/foo", "lib1", "lib2"]:
                    save(self, os.path.join(self.package_folder, p, "file"), "")

            def package_info(self):
                self.cpp_info.includedirs = ["inc1", "inc2", "inc3/foo"]
                self.cpp_info.libdirs = ["lib1", "lib2"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")
    client.run("install --requires=pkg/0.1@ -g MakeDeps")

    makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
    assert "CONAN_INCLUDE_DIRS_PKG = \\\n" \
           "\t$(CONAN_INCLUDE_DIR_FLAG)$(CONAN_ROOT_PKG)/inc1 \\\n" \
           "\t$(CONAN_INCLUDE_DIR_FLAG)$(CONAN_ROOT_PKG)/inc2 \\\n" \
           "\t$(CONAN_INCLUDE_DIR_FLAG)$(CONAN_ROOT_PKG)/inc3/foo\n" in makefile_content
    assert "CONAN_LIB_DIRS_PKG = \\\n" \
           "\t$(CONAN_LIB_DIR_FLAG)$(CONAN_ROOT_PKG)/lib1 \\\n" \
           "\t$(CONAN_LIB_DIR_FLAG)$(CONAN_ROOT_PKG)/lib2\n" in makefile_content
    assert "CONAN_INCLUDE_DIRS = $(CONAN_INCLUDE_DIRS_PKG)\n" in makefile_content
    assert "CONAN_LIB_DIRS = $(CONAN_LIB_DIRS_PKG)\n" in makefile_content


def test_make_with_public_deps_and_component_requires():
    """
    Testing a complex structure like:

    * lib/0.1
        - Components: "cmp1"
    * other/0.1
    * second/0.1
        - Requires: "lib/0.1"
        - Components: "mycomponent", "myfirstcomp"
            + "mycomponent" requires "lib::cmp1"
            + "myfirstcomp" requires "mycomponent"
    * third/0.1
        - Requires: "second/0.1", "other/0.1"
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=lib --version=0.1")
    client.save({"conanfile.py": GenConanfile("other", "0.1").with_package_file("file.h", "0.1")})
    client.run("create .")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestMakeDepsConan(ConanFile):
            requires = "lib/0.1"

            def package_info(self):
                self.cpp_info.components["mycomponent"].requires.append("lib::cmp1")
                self.cpp_info.components["myfirstcomp"].requires.append("mycomponent")
                self.cpp_info.components["myfirstcomp"].set_property("my_prop", "my prop value")
                self.cpp_info.components["myfirstcomp"].set_property("my_prop_with_newline", "my\\nprop")

        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . --name=second --version=0.1")
    client.save({"conanfile.py": GenConanfile("third", "0.1").with_package_file("file.h", "0.1")
                                                             .with_require("second/0.1")
                                                             .with_require("other/0.1")},
                clean_first=True)
    client.run("create .")

    client2 = TestClient(cache_folder=client.cache_folder)
    conanfile = textwrap.dedent("""
        [requires]
        third/0.1

        [generators]
        MakeDeps
        """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")

    makefile_content = client2.load(CONAN_MAKEFILE_FILENAME)
    assert "CONAN_DEPS = \\\n" \
           "\tthird \\\n" \
           "\tsecond \\\n" \
           "\tlib \\\n" \
           "\tother\n" in makefile_content
    assert 'CONAN_REQUIRES_SECOND = \\\n' \
           '\t$(CONAN_REQUIRES_SECOND_MYCOMPONENT) \\\n' \
           '\t$(CONAN_REQUIRES_SECOND_MYFIRSTCOMP)\n' in makefile_content
    assert 'SYSROOT' not in makefile_content
    assert 'CONAN_REQUIRES_SECOND_MYFIRSTCOMP = mycomponent\n' in makefile_content
    assert 'CONAN_LIBS_LIB = $(CONAN_LIBS_LIB_CMP1)\n'in makefile_content

    assert 'CONAN_COMPONENTS_LIB = cmp1\n' in makefile_content
    assert 'CONAN_LIBS_LIB_CMP1 = $(CONAN_LIB_FLAG)libcmp1\n' in makefile_content
    assert 'CONAN_REQUIRES = $(CONAN_REQUIRES_SECOND)\n' in makefile_content
    assert 'CONAN_LIBS = $(CONAN_LIBS_LIB)\n' in makefile_content

    assert 'CONAN_PROPERTY_SECOND_MYFIRSTCOMP_MY_PROP = my prop value\n' in makefile_content
    assert 'CONAN_PROPERTY_SECOND_MYFIRSTCOMP_MY_PROP_WITH_NEWLINE' not in makefile_content
    assert "WARN: Skipping propery 'my_prop_with_newline' because it contains newline" in client2.stderr


def test_make_with_public_deps_and_component_requires_second():
    """
    Testing another complex structure like:

    * other/0.1
        - Components: "cmp1", "cmp2", "cmp3"
            + "cmp1" (it shouldn't be affected by "other")
            + "cmp3" (it shouldn't be affected by "other")
            + "cmp3" requires "cmp1"
    * pkg/0.1
        - Requires: "other/0.1" -> "other::cmp1"
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["other_cmp1"]
                self.cpp_info.components["cmp2"].libs = ["other_cmp2"]
                self.cpp_info.components["cmp3"].requires.append("cmp1")
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=other --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestMakeDepsConan(ConanFile):
            requires = "other/1.0"

            def package_info(self):
                self.cpp_info.requires = ["other::cmp1"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")

    client2 = TestClient(cache_folder=client.cache_folder)
    conanfile = textwrap.dedent("""
        [requires]
        pkg/0.1

        [generators]
        MakeDeps
        """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")
    make_content = client2.load(CONAN_MAKEFILE_FILENAME)
    assert 'CONAN_REQUIRES_PKG = other::cmp1\n' in make_content
    assert 'CONAN_REQUIRES_OTHER = $(CONAN_REQUIRES_OTHER_CMP3)\n' in make_content
    assert 'CONAN_REQUIRES_OTHER_CMP3 = cmp1\n' in make_content
    assert 'CONAN_COMPONENTS_OTHER = \\\n\tcmp1 \\\n\tcmp2 \\\n\tcmp3\n' in make_content
    assert 'CONAN_LIBS_OTHER = \\\n\t$(CONAN_LIBS_OTHER_CMP1) \\\n\t$(CONAN_LIBS_OTHER_CMP2)\n' in make_content
    assert 'CONAN_LIBS_OTHER_CMP1 = $(CONAN_LIB_FLAG)other_cmp1\n' in make_content
    assert 'CONAN_LIBS_OTHER_CMP2 = $(CONAN_LIB_FLAG)other_cmp2\n' in make_content
    assert 'CONAN_LIBS = $(CONAN_LIBS_OTHER)\n' in make_content
    assert 'CONAN_REQUIRES = \\\n\t$(CONAN_REQUIRES_PKG) \\\n\t$(CONAN_REQUIRES_OTHER)\n' in make_content


def test_makedeps_with_test_requires():
    """
    MakeDeps has to create any test requires to be declared on the recipe.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class TestMakeDeps(ConanFile):
            def package_info(self):
                self.cpp_info.libs = [f"lib{self.name}"]
        """)

    client.save({"conanfile.py": conanfile})
    client.run("create . --name=app --version=1.0")
    client.run("create . --name=test --version=1.0")
    # Create library having build and test requires
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class HelloLib(ConanFile):
            def build_requirements(self):
                self.tool_requires('app/1.0')
                self.test_requires('test/1.0')
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g MakeDeps")
    assert 'CONAN_DEPS = test\n' in client.load(CONAN_MAKEFILE_FILENAME)
    assert 'app' not in client.load(CONAN_MAKEFILE_FILENAME)


def test_makedeps_with_editable_layout():
    """
    The MakeDeps should be supported with editable layour mode
    """
    client = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        class Dep(ConanFile):
            name = "dep"
            version = "0.1"
            def layout(self):
                self.cpp.source.includedirs = ["include"]
            def package_info(self):
                self.cpp_info.libs = ["mylib"]
        """)
    client.save({"dep/conanfile.py": dep,
                 "dep/include/header.h": "",
                 "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/0.1")})
    client.run("create dep")
    client.run("editable add dep")
    with client.chdir("pkg"):
        client.run("install . -g MakeDeps")
        makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
        assert 'CONAN_LIBS_DEP = $(CONAN_LIB_FLAG)mylib\n' in makefile_content
        assert 'CONAN_INCLUDE_DIRS_DEP = $(CONAN_INCLUDE_DIR_FLAG)$(CONAN_ROOT_DEP)/include\n' in makefile_content


def test_makedeps_tool_requires():
    """
    Testing if MakeDeps are created for tool requires
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestMakeDepsConan(ConanFile):

            def package_info(self):
                self.cpp_info.libs = ["libtool"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name tool --version 1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestMakeDepsConan(ConanFile):

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["other_cmp1"]
                self.cpp_info.components["cmp2"].libs = ["other_cmp2"]
                self.cpp_info.components["cmp3"].requires.append("cmp1")
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . --name other --version 1.0")

    conanfile = textwrap.dedent("""
        [tool_requires]
        tool/1.0
        other/1.0
        [generators]
        MakeDeps
        """)
    client.save({"conanfile.txt": conanfile}, clean_first=True)
    client.run("install . -pr:h default -pr:b default")
    make_content = client.load(CONAN_MAKEFILE_FILENAME)

    # TODO: MakeDeps should support tool_requires in the future
    assert "CONAN_LIBS_TOOL" not in make_content
    assert "CONAN_NAME_OTHER" not in make_content


@pytest.mark.parametrize("pattern, result, expected",
                         [("libs = []", False, 'SYSROOT'),
                          ("sysroot = ['/foo/bar/sysroot']", True, 'CONAN_SYSROOT_PACKAGE = /foo/bar/sysroot')])
def test_makefile_sysroot(pattern, result, expected):
    """
    The MakeDeps should not enforce sysroot in case not defined
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            class TestMakeDepsConan(ConanFile):
                def package_info(self):
                    self.cpp_info.{{ pattern }}
            """)
    client.save({"conanfile.py": conanfile.replace("{{ pattern }}", pattern)})
    client.run("create . --name package --version 0.1.0")
    client.run("install --requires=package/0.1.0 -pr:h default -pr:b default -g MakeDeps")
    makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
    assert (expected in makefile_content) == result


def test_makefile_reference():
    """
    The MakeDeps should generate the correct package reference as variable
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Testing(ConanFile):
                pass
            """)
    client.save({"conanfile.py": conanfile})

    # official packages <name>/<version>
    client.run("create . --name package --version 0.1.0")
    client.run("install --requires=package/0.1.0 -pr:h default -pr:b default -g MakeDeps")
    makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
    assert 'CONAN_REFERENCE_PACKAGE = package/0.1.0\n' in makefile_content

    # custom packages <name>/<version>@<user>/<channel>
    client.run("create . --name package --version 0.1.0 --user user --channel channel")
    client.run("install --requires=package/0.1.0@user/channel -pr:h default -pr:b default -g MakeDeps")
    makefile_content = client.load(CONAN_MAKEFILE_FILENAME)
    assert 'CONAN_REFERENCE_PACKAGE = package/0.1.0@user/channel\n' in makefile_content
