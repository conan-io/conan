import glob
import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load


def get_requires_from_content(content):
    for line in content.splitlines():
        if "Requires:" in line:
            return line
    return ""


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

    assert 'Name: MyLib' in pc_content
    assert 'Description: Conan package: MyLib' in pc_content
    assert 'Version: 0.1' in pc_content
    assert 'Libs: -L"${libdir1}" -L"${libdir2}"' in pc_content
    assert 'Cflags: -I"${includedir1}"' in pc_content

    def assert_is_abs(path):
        assert os.path.isabs(path) is True

    for line in pc_content.splitlines():
        if line.startswith("includedir1="):
            assert_is_abs(line[len("includedir1="):])
            assert line.endswith("include")
        elif line.startswith("libdir1="):
            assert_is_abs(line[len("libdir1="):])
            assert line.endswith("lib")
        elif line.startswith("libdir2="):
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
    assert 'Libs: -L"${libdir1}" -lmylib1 -lmylib2 -lsystem_lib1 -lsystem_lib2' in pc_content


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


def test_custom_content_and_version_components():
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os
        import textwrap

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.components["mycomponent"].set_property("pkg_config_custom_content",
                                                                     "componentdir=${prefix}/mydir")
                self.cpp_info.components["mycomponent"].set_property("component_version",
                                                                     "19.8.199")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@")
    client.run("install pkg/0.1@ -g PkgConfigDeps")
    pc_content = client.load("pkg-mycomponent.pc")
    assert "componentdir=${prefix}/mydir" in pc_content
    assert "Version: 19.8.199" in pc_content


def test_pkg_with_public_deps_and_component_requires():
    """
    Testing a complex structure like:

    * first/0.1
        - Global pkg_config_name == "myfirstlib"
        - Components: "cmp1"
    * other/0.1
    * second/0.1
        - Requires: "first/0.1"
        - Components: "mycomponent", "myfirstcomp"
            + "mycomponent" requires "first::cmp1"
            + "myfirstcomp" requires "mycomponent"
    * third/0.1
        - Requires: "second/0.1", "other/0.1"

    Expected file structure after running PkgConfigDeps as generator:
        - other.pc
        - myfirstlib-cmp1.pc
        - myfirstlib.pc
        - second-mycomponent.pc
        - second-myfirstcomp.pc
        - second.pc
        - third.pc
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "myfirstlib")
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . first/0.1@")
    client.save({"conanfile.py": GenConanfile("other", "0.1").with_package_file("file.h", "0.1")})
    client.run("create .")

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "first/0.1"

            def package_info(self):
                self.cpp_info.components["mycomponent"].requires.append("first::cmp1")
                self.cpp_info.components["myfirstcomp"].requires.append("mycomponent")

        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . second/0.1@")
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
        PkgConfigDeps
        """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")

    pc_content = client2.load("third.pc")
    # Originally posted: https://github.com/conan-io/conan/issues/9939
    assert "Requires: second other" == get_requires_from_content(pc_content)
    pc_content = client2.load("second.pc")
    assert "Requires: second-mycomponent second-myfirstcomp" == get_requires_from_content(pc_content)
    pc_content = client2.load("second-mycomponent.pc")
    assert "Requires: myfirstlib-cmp1" == get_requires_from_content(pc_content)
    pc_content = client2.load("second-myfirstcomp.pc")
    assert "Requires: second-mycomponent" == get_requires_from_content(pc_content)
    pc_content = client2.load("myfirstlib.pc")
    assert "Requires: myfirstlib-cmp1" == get_requires_from_content(pc_content)
    pc_content = client2.load("other.pc")
    assert "" == get_requires_from_content(pc_content)


def test_pkg_with_public_deps_and_component_requires_2():
    """
    Testing another complex structure like:

    * other/0.1
        - Global pkg_config_name == "fancy_name"
        - Components: "cmp1", "cmp2", "cmp3"
            + "cmp1" pkg_config_name == "component1" (it shouldn't be affected by "fancy_name")
            + "cmp3" pkg_config_name == "component3" (it shouldn't be affected by "fancy_name")
            + "cmp3" requires "cmp1"
    * pkg/0.1
        - Requires: "other/0.1" -> "other::cmp1"

    Expected file structure after running PkgConfigDeps as generator:
        - component1.pc
        - component3.pc
        - other-cmp2.pc
        - other.pc
        - pkg.pc
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "fancy_name")
                self.cpp_info.components["cmp1"].libs = ["other_cmp1"]
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "component1")
                self.cpp_info.components["cmp2"].libs = ["other_cmp2"]
                self.cpp_info.components["cmp3"].requires.append("cmp1")
                self.cpp_info.components["cmp3"].set_property("pkg_config_name", "component3")
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
    assert "Requires: component1" == get_requires_from_content(pc_content)
    pc_content = client2.load("fancy_name.pc")
    assert "Requires: component1 fancy_name-cmp2 component3" == get_requires_from_content(pc_content)
    assert client2.load("component1.pc")
    assert client2.load("fancy_name-cmp2.pc")
    pc_content = client2.load("component3.pc")
    assert "Requires: component1" == get_requires_from_content(pc_content)


def test_pkg_config_name_full_aliases():
    """
    Testing a simpler structure but paying more attention into several aliases.
    Expected file structure after running PkgConfigDeps as generator:
        - compo1.pc
        - compo1_alias.pc
        - pkg_alias1.pc
        - pkg_alias2.pc
        - pkg_other_name.pc
        - second-mycomponent.pc
        - second.pc
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "pkg_other_name")
                self.cpp_info.set_property("pkg_config_aliases", ["pkg_alias1", "pkg_alias2"])
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "compo1")
                self.cpp_info.components["cmp1"].set_property("pkg_config_aliases", ["compo1_alias"])
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . first/0.3@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "first/0.3"

            def package_info(self):
                self.cpp_info.components["mycomponent"].requires.append("first::cmp1")

        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . second/0.2@")

    conanfile = textwrap.dedent("""
        [requires]
        second/0.2

        [generators]
        PkgConfigDeps
        """)
    client.save({"conanfile.txt": conanfile}, clean_first=True)
    client.run("install .")

    pc_content = client.load("compo1.pc")
    assert "Description: Conan component: pkg_other_name-compo1" in pc_content
    assert "Requires" not in pc_content

    pc_content = client.load("compo1_alias.pc")
    content = textwrap.dedent("""\
    Name: compo1_alias
    Description: Alias compo1_alias for compo1
    Version: 0.3
    Requires: compo1
    """)
    assert content == pc_content

    pc_content = client.load("pkg_other_name.pc")
    assert "Description: Conan package: pkg_other_name" in pc_content
    assert "Requires: compo1" in pc_content

    pc_content = client.load("pkg_alias1.pc")
    content = textwrap.dedent("""\
    Name: pkg_alias1
    Description: Alias pkg_alias1 for pkg_other_name
    Version: 0.3
    Requires: pkg_other_name
    """)
    assert content == pc_content

    pc_content = client.load("pkg_alias2.pc")
    content = textwrap.dedent("""\
    Name: pkg_alias2
    Description: Alias pkg_alias2 for pkg_other_name
    Version: 0.3
    Requires: pkg_other_name
    """)
    assert content == pc_content

    pc_content = client.load("second-mycomponent.pc")
    assert "Requires: compo1" == get_requires_from_content(pc_content)


def test_duplicated_names_warnings():
    """
    Testing some WARN messages if there are duplicated pkg_config_name/pkg_config_aliases defined

    Scenario: consumer -> pkga/1.0 -> pkgb/1.0
    Expected WARN cases:
        - Duplicated aliases.
        - Duplicated names, alias and component name
        - Duplicated components names.
        - Duplicated package and component name.
        - Duplicated names between different dependencies.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "libpkg")
                # Duplicated components
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "component1")
                self.cpp_info.components["cmp2"].set_property("pkg_config_name", "component1")
                # Duplicated package and component name
                self.cpp_info.components["cmp3"].set_property("pkg_config_name", "libpkg")
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . pkgb/1.0@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "pkgb/1.0"

            def package_info(self):
                # Duplicated name as pkgb
                self.cpp_info.set_property("pkg_config_name", "libpkg")
                self.cpp_info.components["cmp1"].requires.append("pkgb::cmp1")
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "component1")
                # Duplicated aliases
                self.cpp_info.components["cmp2"].set_property("pkg_config_aliases", ["alias1"])
                self.cpp_info.components["cmp3"].set_property("pkg_config_aliases", ["alias1"])
                # Duplicated names, alias and component name
                self.cpp_info.components["cmp2"].set_property("pkg_config_name", "libcmp")
                self.cpp_info.components["cmp4"].set_property("pkg_config_aliases", ["libcmp"])
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . pkga/1.0@")

    conanfile = textwrap.dedent("""
        [requires]
        pkga/1.0

        [generators]
        PkgConfigDeps
        """)
    client.save({"conanfile.txt": conanfile}, clean_first=True)
    client.run("install .")
    output = client.out
    # Duplicated aliases from pkga
    assert "WARN: [pkga/1.0] The PC alias name alias1.pc already exists and it matches with " \
           "another alias one" in output
    # Duplicated names, alias and component name from pkga
    # Issue related: https://github.com/conan-io/conan/issues/10341
    assert "WARN: [pkga/1.0] The PC alias name libcmp.pc already exists and it matches with " \
           "another package/component one" in output
    # Duplicated components from pkgb
    assert "WARN: [pkgb/1.0] The PC component name component1.pc already exists and it matches " \
           "with another component one" in output
    # Duplicated package and component name from pkgb
    assert "WARN: [pkgb/1.0] The PC package name libpkg.pc already exists and it matches with " \
           "another component one" in output
    # Duplicated names between pkgb and pkga
    assert "WARN: [pkgb/1.0] The PC file name component1.pc already exists and it matches with " \
           "another name/alias declared in pkga/1.0 package" in output
    assert "WARN: [pkgb/1.0] The PC file name libpkg.pc already exists and it matches with " \
           "another name/alias declared in pkga/1.0 package" in output
    pc_files = [os.path.basename(i) for i in glob.glob(os.path.join(client.current_folder, '*.pc'))]
    pc_files.sort()
    # Let's check all the PC file names created just in case
    assert pc_files == ['alias1.pc', 'component1.pc', 'libcmp.pc', 'libpkg-cmp3.pc',
                        'libpkg-cmp4.pc', 'libpkg.pc']


def test_components_and_package_pc_creation_order():
    """
    Testing if the root package PC file name matches with any of the components one, the first one
    is not going to be created. Components have more priority than root package.

    Issue related: https://github.com/conan-io/conan/issues/10341
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "OpenCL")
                self.cpp_info.components["_opencl-headers"].set_property("pkg_config_name", "OpenCL")
                self.cpp_info.components["_opencl-other"].set_property("pkg_config_name", "OtherCL")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . opencl/1.0@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "opencl/1.0"

            def package_info(self):
                self.cpp_info.components["comp"].set_property("pkg_config_name", "pkgb")
                self.cpp_info.components["comp"].requires.append("opencl::_opencl-headers")
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . pkgb/1.0@")

    conanfile = textwrap.dedent("""
        [requires]
        pkgb/1.0

        [generators]
        PkgConfigDeps
        """)
    client.save({"conanfile.txt": conanfile}, clean_first=True)
    client.run("install .")
    pc_files = [os.path.basename(i) for i in glob.glob(os.path.join(client.current_folder, '*.pc'))]
    pc_files.sort()
    # Let's check all the PC file names created just in case
    assert pc_files == ['OpenCL.pc', 'OtherCL.pc', 'pkgb.pc']
    pc_content = client.load("OpenCL.pc")
    assert "Name: OpenCL" in pc_content
    assert "Description: Conan component: OpenCL" in pc_content
    assert "Requires:" not in pc_content
    pc_content = client.load("pkgb.pc")
    assert "Requires: OpenCL" in get_requires_from_content(pc_content)
