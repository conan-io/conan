import glob
import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
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
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
            name = "mylib"
            version = "0.1"

            def package_info(self):
                self.cpp_info.frameworkdirs = []
                self.cpp_info.filter_empty = False
                libname = "mylib"
                fake_dir = os.path.join("/", "my_absoulte_path", "fake")
                include_dir = os.path.join(fake_dir, libname, "include")
                lib_dir = os.path.join(fake_dir, libname, "lib")
                lib_dir1 = os.path.join(self.package_folder, "lib2")
                self.cpp_info.includedirs = [include_dir]
                self.cpp_info.libdirs = [lib_dir, lib_dir1]
                self.cpp_info.bindirs = ["mybin"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.run("install --requires=mylib/0.1@ -g PkgConfigDeps")

    pc_path = os.path.join(client.current_folder, "mylib.pc")
    assert os.path.exists(pc_path) is True
    pc_content = load(pc_path)
    assert 'Name: mylib' in pc_content
    assert 'Description: Conan package: mylib' in pc_content
    assert 'Version: 0.1' in pc_content
    assert 'Libs: -L"${libdir}" -L"${libdir1}"' in pc_content
    assert 'Cflags: -I"${includedir}"' in pc_content
    # https://github.com/conan-io/conan/pull/13623
    assert 'bindir=${prefix}/mybin' in pc_content

    def assert_is_abs(path):
        assert os.path.isabs(path) is True

    for line in pc_content.splitlines():
        if line.startswith("includedir="):
            assert_is_abs(line[len("includedir="):])
            assert line.endswith("include")
        elif line.startswith("libdir="):
            assert_is_abs(line[len("libdir="):])
            assert line.endswith("lib")
        elif line.startswith("libdir1="):
            assert "${prefix}/lib2" in line


def test_empty_dirs():
    # Adding in package_info all the empty directories
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
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
    client.run("install --requires=mylib/0.1@ -g PkgConfigDeps")

    pc_path = os.path.join(client.current_folder, "mylib.pc")
    assert os.path.exists(pc_path) is True
    pc_content = load(pc_path)
    expected = textwrap.dedent("""
        Name: mylib
        Description: Conan package: mylib
        Version: 0.1""")
    assert "\n".join(pc_content.splitlines()[1:]) == expected


def test_system_libs():
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os

        class PkgConfigConan(ConanFile):
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
    client.run("install --requires=mylib/0.1@ -g PkgConfigDeps")

    pc_content = client.load("mylib.pc")
    assert 'Libs: -L"${libdir}" -lmylib1 -lmylib2 -lsystem_lib1 -lsystem_lib2' in pc_content


def test_multiple_include():
    # https://github.com/conan-io/conan/issues/7056
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os

        class PkgConfigConan(ConanFile):
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
    client.run("install --requires=pkg/0.1@ -g PkgConfigDeps")

    pc_content = client.load("pkg.pc")
    assert "includedir=${prefix}/inc1" in pc_content
    assert "includedir1=${prefix}/inc2" in pc_content
    assert "includedir2=${prefix}/inc3/foo" in pc_content
    assert "libdir=${prefix}/lib1" in pc_content
    assert "libdir1=${prefix}/lib2" in pc_content
    assert 'Libs: -L"${libdir}" -L"${libdir1}"' in pc_content
    assert 'Cflags: -I"${includedir}" -I"${includedir1}" -I"${includedir2}"' in pc_content


def test_custom_content():
    # https://github.com/conan-io/conan/issues/7661
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os
        import textwrap

        class PkgConfigConan(ConanFile):

            def package(self):
                save(self, os.path.join(self.package_folder, "include" ,"file"), "")
                save(self, os.path.join(self.package_folder, "lib" ,"file"), "")

            def package_info(self):
                custom_content = textwrap.dedent(\"""
                        bindir=${prefix}/my/bin/folder
                        fakelibdir=${prefix}/my/lib/folder
                        datadir=${prefix}/share
                        schemasdir=${datadir}/mylib/schemas
                    \""")
                self.cpp_info.set_property("pkg_config_custom_content", custom_content)
                self.cpp_info.includedirs = ["include"]
                self.cpp_info.libdirs = ["lib"]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")
    client.run("install --requires=pkg/0.1@ -g PkgConfigDeps")

    pc_content = client.load("pkg.pc")
    prefix = pc_content.splitlines()[0]
    expected = textwrap.dedent(f"""\
    {prefix}
    libdir=${{prefix}}/lib
    includedir=${{prefix}}/include
    bindir=${{prefix}}/my/bin/folder
    fakelibdir=${{prefix}}/my/lib/folder
    datadir=${{prefix}}/share
    schemasdir=${{datadir}}/mylib/schemas

    Name: pkg
    Description: Conan package: pkg
    Version: 0.1
    Libs: -L"${{libdir}}"
    Cflags: -I"${{includedir}}"
    """)
    assert expected == pc_content


def test_custom_content_and_version_components():
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.components["mycomponent"].set_property("pkg_config_custom_content",
                                                                     "componentdir=${prefix}/mydir")
                self.cpp_info.components["mycomponent"].set_property("component_version",
                                                                     "19.8.199")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")
    client.run("install --requires=pkg/0.1@ -g PkgConfigDeps")
    pc_content = client.load("pkg-mycomponent.pc")
    assert "componentdir=${prefix}/mydir" in pc_content
    assert "Version: 19.8.199" in pc_content

    # Now with lockfile
    # https://github.com/conan-io/conan/issues/16197
    lockfile = textwrap.dedent("""
        {
            "version": "0.5",
            "requires": [
                "pkg/0.1#9a5fed2bf506fd28817ddfbc92b07fc1"
            ]
        }
        """)
    client.save({"conan.lock": lockfile})
    client.run("install --requires=pkg/0.1 -g PkgConfigDeps --lockfile=conan.lock")
    pc_content = client.load("pkg-mycomponent.pc")
    assert "componentdir=${prefix}/mydir" in pc_content
    assert "Version: 19.8.199" in pc_content


def test_custom_version():
    # https://github.com/conan-io/conan/issues/16197
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
            def package_info(self):
                self.cpp_info.set_property("system_package_version", "19.8.199")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")
    client.run("install --requires=pkg/0.1 -g PkgConfigDeps")

    pc_content = client.load("pkg.pc")
    assert "Version: 19.8.199" in pc_content

    # Now with lockfile
    # https://github.com/conan-io/conan/issues/16197
    lockfile = textwrap.dedent("""
        {
            "version": "0.5",
            "requires": [
                "pkg/0.1#0fe93a852dd6a177bca87cb2d4491a18"
            ]
        }
        """)
    client.save({"conan.lock": lockfile})
    client.run("install --requires=pkg/0.1 -g PkgConfigDeps --lockfile=conan.lock")
    pc_content = client.load("pkg.pc")
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
        from conan import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "myfirstlib")
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=first --version=0.1")
    client.save({"conanfile.py": GenConanfile("other", "0.1").with_package_file("file.h", "0.1")})
    client.run("create .")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "first/0.1"

            def package_info(self):
                self.cpp_info.components["mycomponent"].requires.append("first::cmp1")
                self.cpp_info.components["myfirstcomp"].requires.append("mycomponent")

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
        from conan import ConanFile

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
    client.run("create . --name=other --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
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
        import textwrap
        from conan import ConanFile

        class Recipe(ConanFile):

            def package_info(self):
                custom_content = textwrap.dedent(\"""
                datadir=${prefix}/share
                schemasdir=${datadir}/mylib/schemas
                \""")
                self.cpp_info.set_property("pkg_config_name", "pkg_other_name")
                self.cpp_info.set_property("pkg_config_aliases", ["pkg_alias1", "pkg_alias2"])
                # Custom content only added to root pc file -> pkg_other_name.pc
                self.cpp_info.set_property("pkg_config_custom_content", custom_content)
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "compo1")
                self.cpp_info.components["cmp1"].set_property("pkg_config_aliases", ["compo1_alias"])
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=first --version=0.3")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "first/0.3"

            def package_info(self):
                self.cpp_info.components["mycomponent"].requires.append("first::cmp1")

        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . --name=second --version=0.2")

    conanfile = textwrap.dedent("""
        [requires]
        second/0.2

        [generators]
        PkgConfigDeps
        """)
    client.save({"conanfile.txt": conanfile}, clean_first=True)
    client.run("install .")

    pc_content = client.load("compo1.pc")
    prefix = pc_content.splitlines()[0]
    assert "Description: Conan component: pkg_other_name-compo1" in pc_content
    assert "Requires" not in pc_content

    pc_content = client.load("compo1_alias.pc")
    content = textwrap.dedent(f"""\
    {prefix}

    Name: compo1_alias
    Description: Alias compo1_alias for compo1
    Version: 0.3
    Requires: compo1
    """)
    assert content == pc_content

    pc_content = client.load("pkg_other_name.pc")
    content = textwrap.dedent(f"""\
    {prefix}
    libdir=${{prefix}}/lib
    includedir=${{prefix}}/include
    bindir=${{prefix}}/bin
    datadir=${{prefix}}/share
    schemasdir=${{datadir}}/mylib/schemas

    Name: pkg_other_name
    Description: Conan package: pkg_other_name
    Version: 0.3
    Libs: -L"${{libdir}}"
    Cflags: -I"${{includedir}}"
    Requires: compo1
    """)
    assert content == pc_content

    pc_content = client.load("pkg_alias1.pc")
    content = textwrap.dedent(f"""\
    {prefix}

    Name: pkg_alias1
    Description: Alias pkg_alias1 for pkg_other_name
    Version: 0.3
    Requires: pkg_other_name
    """)
    assert content == pc_content

    pc_content = client.load("pkg_alias2.pc")
    content = textwrap.dedent(f"""\
    {prefix}

    Name: pkg_alias2
    Description: Alias pkg_alias2 for pkg_other_name
    Version: 0.3
    Requires: pkg_other_name
    """)
    assert content == pc_content

    pc_content = client.load("second-mycomponent.pc")
    assert "Requires: compo1" == get_requires_from_content(pc_content)


def test_components_and_package_pc_creation_order():
    """
    Testing if the root package PC file name matches with any of the components one, the first one
    is not going to be created. Components have more priority than root package.

    Issue related: https://github.com/conan-io/conan/issues/10341
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "OpenCL")
                self.cpp_info.components["_opencl-headers"].set_property("pkg_config_name", "OpenCL")
                self.cpp_info.components["_opencl-other"].set_property("pkg_config_name", "OtherCL")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=opencl --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
            requires = "opencl/1.0"

            def package_info(self):
                self.cpp_info.components["comp"].set_property("pkg_config_name", "pkgb")
                self.cpp_info.components["comp"].requires.append("opencl::_opencl-headers")
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . --name=pkgb --version=1.0")

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


def test_pkgconfigdeps_with_test_requires():
    """
    PkgConfigDeps has to create any test requires declared on the recipe.

    Related issue: https://github.com/conan-io/conan/issues/11376
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.cpp_info.libs = ["lib%s"]
        """)
    with client.chdir("app"):
        client.save({"conanfile.py": conanfile % "app"})
        client.run("create . --name=app --version=1.0")
    with client.chdir("test"):
        client.save({"conanfile.py": conanfile % "test"})
        client.run("create . --name=test --version=1.0")
    # Create library having build and test requires
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class HelloLib(ConanFile):
            def build_requirements(self):
                self.test_requires('app/1.0')
                self.test_requires('test/1.0')
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g PkgConfigDeps")
    assert "Description: Conan package: test" in client.load("test.pc")
    assert "Description: Conan package: app" in client.load("app.pc")


def test_with_editable_layout():
    """
    https://github.com/conan-io/conan/issues/11435
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
        client.run("install . -g PkgConfigDeps")
        pc = client.load("dep.pc")
        assert 'Libs: -L"${libdir}" -lmylib' in pc
        assert 'includedir=' in pc
        assert 'Cflags: -I"${includedir}"' in pc


def test_tool_requires():
    """
    Testing if PC files are created for tool requires if build_context_activated/_suffix is used.

    Issue related: https://github.com/conan-io/conan/issues/11710
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.libs = ["libtool"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name tool --version 1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "libother")
                self.cpp_info.components["cmp1"].libs = ["other_cmp1"]
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "component1")
                self.cpp_info.components["cmp2"].libs = ["other_cmp2"]
                self.cpp_info.components["cmp3"].requires.append("cmp1")
                self.cpp_info.components["cmp3"].set_property("pkg_config_name", "component3")
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . --name other --version 1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import PkgConfigDeps

        class PkgConfigConan(ConanFile):
            name = "demo"
            version = "1.0"

            def build_requirements(self):
                self.build_requires("tool/1.0")
                self.build_requires("other/1.0")

            def generate(self):
                tc = PkgConfigDeps(self)
                tc.build_context_activated = ["other", "tool"]
                tc.build_context_suffix = {"tool": "_bt", "other": "_bo"}
                tc.generate()
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -pr:h default -pr:b default")
    pc_files = [os.path.basename(i) for i in glob.glob(os.path.join(client.current_folder, '*.pc'))]
    pc_files.sort()
    # Let's check all the PC file names created just in case
    assert pc_files == ['component1_bo.pc', 'component3_bo.pc',
                        'libother_bo-cmp2.pc', 'libother_bo.pc', 'tool_bt.pc']
    pc_content = client.load("tool_bt.pc")
    assert "Name: tool_bt" in pc_content
    pc_content = client.load("libother_bo.pc")
    assert "Name: libother_bo" in pc_content
    assert "Requires: component1_bo libother_bo-cmp2 component3_bo" == get_requires_from_content(pc_content)
    pc_content = client.load("component1_bo.pc")
    assert "Name: component1_bo" in pc_content
    pc_content = client.load("libother_bo-cmp2.pc")
    assert "Name: libother_bo-cmp2" in pc_content
    pc_content = client.load("component3_bo.pc")
    assert "Name: component3_bo" in pc_content
    assert "Requires: component1_bo" == get_requires_from_content(pc_content)


def test_tool_requires_not_created_if_no_activated():
    """
    Testing if there are no PC files created in no context are activated
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.libs = ["libtool"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name tool --version 1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):
            name = "demo"
            version = "1.0"
            generators = "PkgConfigDeps"

            def build_requirements(self):
                self.build_requires("tool/1.0")

        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -pr:h default -pr:b default")
    pc_files = [os.path.basename(i) for i in glob.glob(os.path.join(client.current_folder, '*.pc'))]
    pc_files.sort()
    assert pc_files == []


def test_tool_requires_error_if_no_build_suffix():
    """
    Testing if same dependency exists in both require and build require (without suffix)
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgConfigConan(ConanFile):

            def package_info(self):
                self.cpp_info.libs = ["libtool"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name tool --version 1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import PkgConfigDeps

        class PkgConfigConan(ConanFile):
            name = "demo"
            version = "1.0"

            def requirements(self):
                self.requires("tool/1.0")

            def build_requirements(self):
                self.build_requires("tool/1.0")

            def generate(self):
                tc = PkgConfigDeps(self)
                tc.build_context_activated = ["tool"]
                tc.generate()
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -pr:h default -pr:b default", assert_error=True)
    assert "The packages ['tool'] exist both as 'require' and as 'build require'" in client.out


def test_error_missing_pc_build_context():
    """
    PkgConfigDeps was failing, not generating the zlib.pc in the
    build context, for a test_package that both requires(example/1.0) and
    tool_requires(example/1.0), which depends on zlib
    # https://github.com/conan-io/conan/issues/12664
    """
    c = TestClient()
    example = textwrap.dedent("""
        import os
        from conan import ConanFile
        class Example(ConanFile):
            name = "example"
            version = "1.0"
            requires = "game/1.0"
            generators = "PkgConfigDeps"
            settings = "build_type"
            def build(self):
                assert os.path.exists("math.pc")
                assert os.path.exists("engine.pc")
                assert os.path.exists("game.pc")
            """)
    c.save({"math/conanfile.py": GenConanfile("math", "1.0").with_settings("build_type"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_settings("build_type")
                                                                .with_require("math/1.0"),
            "game/conanfile.py": GenConanfile("game", "1.0").with_settings("build_type")
                                                            .with_requires("engine/1.0"),
            "example/conanfile.py": example,
            # With ``with_test()`` it already generates a requires(example/1.0)
            "example/test_package/conanfile.py": GenConanfile().with_build_requires("example/1.0")
                                                               .with_test("pass")})
    c.run("create math")
    c.run("create engine")
    c.run("create game")
    # This used to crash because of the assert inside the build() method
    c.run("create example -pr:b=default -pr:h=default")
    # Now make sure we can actually build with build!=host context
    # The debug binaries are missing, so adding --build=missing
    c.run("create example -pr:b=default -pr:h=default -s:h build_type=Debug --build=missing "
          "--build=example")

    c.assert_listed_require({"example/1.0": "Cache"})
    c.assert_listed_require({"example/1.0": "Cache"}, build=True)


class TestPCGenerationBuildContext:
    """
    https://github.com/conan-io/conan/issues/14920
    """
    def test_pc_generate(self):
        c = TestClient()
        tool = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.gnu import PkgConfigDeps

            class Example(ConanFile):
                name = "tool"
                version = "1.0"
                requires = "wayland/1.0"
                tool_requires = "wayland/1.0"

                def generate(self):
                    deps = PkgConfigDeps(self)
                    deps.build_context_activated = ["wayland", "dep"]
                    deps.build_context_suffix = {"wayland": "_BUILD", "dep": "_BUILD"}
                    deps.generate()

                def build(self):
                    assert os.path.exists("wayland.pc")
                    assert os.path.exists("wayland_BUILD.pc")
                    assert os.path.exists("dep.pc")
                    assert os.path.exists("dep_BUILD.pc")
                """)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_package_type("shared-library"),
                "wayland/conanfile.py": GenConanfile("wayland", "1.0").with_requires("dep/1.0"),
                "tool/conanfile.py": tool,
                "app/conanfile.py": GenConanfile().with_tool_requires("tool/1.0")})
        c.run("export dep")
        c.run("export wayland")
        c.run("export tool")
        c.run("install app --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail
        # Deprecation warning!
        assert "PkgConfigDeps.build_context_suffix attribute has been deprecated" in c.out
        # Now make sure we can actually build with build!=host context
        c.run("install app -s:h build_type=Debug --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail

    def test_pc_generate_components(self):
        c = TestClient()
        tool = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.gnu import PkgConfigDeps

            class Example(ConanFile):
                name = "tool"
                version = "1.0"
                requires = "wayland/1.0"
                tool_requires = "wayland/1.0"

                def generate(self):
                    deps = PkgConfigDeps(self)
                    deps.build_context_activated = ["wayland", "dep"]
                    deps.build_context_suffix = {"wayland": "_BUILD", "dep": "_BUILD"}
                    deps.generate()

                def build(self):
                    assert os.path.exists("wayland.pc")
                    assert os.path.exists("wayland-client.pc")
                    assert os.path.exists("wayland-server.pc")
                    assert os.path.exists("wayland_BUILD.pc")
                    assert os.path.exists("wayland_BUILD-client.pc")
                    assert os.path.exists("wayland_BUILD-server.pc")
                    assert os.path.exists("dep.pc")
                    assert os.path.exists("dep_BUILD.pc")

                    # Issue: https://github.com/conan-io/conan/issues/12342
                    # Issue: https://github.com/conan-io/conan/issues/14935
                    assert not os.path.exists("build/wayland.pc")
                    assert not os.path.exists("build/wayland-client.pc")
                    assert not os.path.exists("build/wayland-server.pc")
                    assert not os.path.exists("build/dep.pc")
                """)
        wayland = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                name = "wayland"
                version = "1.0"
                requires = "dep/1.0"

                def package_info(self):
                    self.cpp_info.components["client"].libs = []
                    self.cpp_info.components["server"].libs = []
            """)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_package_type("shared-library"),
                "wayland/conanfile.py": wayland,
                "tool/conanfile.py": tool,
                "app/conanfile.py": GenConanfile().with_tool_requires("tool/1.0")})
        c.run("export dep")
        c.run("export wayland")
        c.run("export tool")
        c.run("install app --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail
        # Now make sure we can actually build with build!=host context
        c.run("install app -s:h build_type=Debug --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail

    @pytest.mark.parametrize("build_folder_name", ["build", ""])
    def test_pc_generate_components_in_build_context_folder(self, build_folder_name):
        c = TestClient()
        tool = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.gnu import PkgConfigDeps

            class Example(ConanFile):
                name = "tool"
                version = "1.0"
                requires = "wayland/1.0"
                tool_requires = "wayland/1.0"

                def generate(self):
                    deps = PkgConfigDeps(self)
                    deps.build_context_activated = ["wayland", "dep"]
                    deps.build_context_folder = "{build_folder_name}"
                    deps.generate()

                def build(self):
                    assert os.path.exists("wayland.pc")
                    assert os.path.exists("wayland-client.pc")
                    assert os.path.exists("wayland-server.pc")
                    assert os.path.exists("dep.pc")

                    # Issue: https://github.com/conan-io/conan/issues/12342
                    # Issue: https://github.com/conan-io/conan/issues/14935
                    if "{build_folder_name}":
                        assert os.path.exists("{build_folder_name}/wayland.pc")
                        assert os.path.exists("{build_folder_name}/wayland-client.pc")
                        assert os.path.exists("{build_folder_name}/wayland-server.pc")
                        assert os.path.exists("{build_folder_name}/dep.pc")
                """.format(build_folder_name=build_folder_name))
        wayland = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                name = "wayland"
                version = "1.0"
                requires = "dep/1.0"

                def package_info(self):
                    self.cpp_info.components["client"].libs = []
                    self.cpp_info.components["server"].libs = []
            """)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_package_type("shared-library"),
                "wayland/conanfile.py": wayland,
                "tool/conanfile.py": tool,
                "app/conanfile.py": GenConanfile().with_tool_requires("tool/1.0")})
        c.run("export dep")
        c.run("export wayland")
        c.run("export tool")
        c.run("install app --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail
        # Now make sure we can actually build with build!=host context
        c.run("install app -s:h build_type=Debug --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail

    @pytest.mark.parametrize("build_folder_name", ["build", ""])
    def test_pkg_config_deps_set_in_build_context_folder(self, build_folder_name):
        c = TestClient()
        tool = textwrap.dedent("""
                    import os
                    from conan import ConanFile
                    from conan.tools.gnu import PkgConfigDeps

                    class Example(ConanFile):
                       name = "tool"
                       version = "1.0"
                       requires = "wayland/1.0"
                       tool_requires = "wayland/1.0"

                    def generate(self):
                       deps = PkgConfigDeps(self)
                       deps.set_property("wayland", "pkg_config_name", "waylandx264")
                       deps.build_context_activated = ["wayland", "dep"]
                       deps.build_context_folder = "{build_folder_name}"
                       deps.generate()

                    def build(self):
                        assert os.path.exists("waylandx264.pc")
                        assert not os.path.exists("wayland.pc")
                        if "{build_folder_name}":
                            assert os.path.exists("{build_folder_name}/waylandx264.pc")
                            assert not os.path.exists("{build_folder_name}/wayland.pc")
                   """.format(build_folder_name=build_folder_name))
        wayland = textwrap.dedent("""
               from conan import ConanFile

               class Pkg(ConanFile):
                   name = "wayland"
                   version = "1.0"
                   requires = "dep/1.0"

                   def package_info(self):
                       self.cpp_info.components["client"].libs = []
                       self.cpp_info.components["server"].libs = []
               """)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_package_type("shared-library"),
                "wayland/conanfile.py": wayland,
                "tool/conanfile.py": tool,
                "app/conanfile.py": GenConanfile().with_tool_requires("tool/1.0")})
        c.run("create dep")
        c.run("create wayland")
        c.run("create tool")
        c.run("install app --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail
        # Now make sure we can actually build with build!=host context
        c.run("install app -s:h build_type=Debug --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail

    def test_tool_requires_error_if_folder_and_suffix(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class PkgConfigConan(ConanFile):

                def package_info(self):
                    self.cpp_info.libs = ["libtool"]
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name tool --version 1.0")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.gnu import PkgConfigDeps

            class PkgConfigConan(ConanFile):
                name = "demo"
                version = "1.0"

                def requirements(self):
                    self.requires("tool/1.0")

                def build_requirements(self):
                    self.build_requires("tool/1.0")

                def generate(self):
                    tc = PkgConfigDeps(self)
                    tc.build_context_activated = ["tool"]
                    tc.build_context_folder = "build"
                    tc.build_context_suffix = {"tool": "_bt"}
                    tc.generate()
            """)
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("install . -pr:h default -pr:b default", assert_error=True)
        assert ("It's not allowed to define both PkgConfigDeps.build_context_folder "
                "and PkgConfigDeps.build_context_suffix (deprecated).") in client.out


def test_pkg_config_deps_and_private_deps():
    """
    Testing that no errors are raised when the dependency tree has a private one in the middle
    of it.

    Issue related: https://github.com/conan-io/conan/issues/15311
    """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("private", "0.1")})
    client.run("create .")
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    class ConsumerConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "PkgConfigDeps"
        name = "pkg"
        version = "0.1"
        def requirements(self):
            self.requires("private/0.1", visible=False)
    """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create .")
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    class ConsumerConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "PkgConfigDeps"

        def requirements(self):
            self.requires("pkg/0.1")
    """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    # Now, it passes and creates the pc files correctly (the skipped one is not created)
    client.run("install .")
    assert "Requires:" not in client.load("pkg.pc")


def test_using_deployer_folder():
    """
    Testing that the absolute path is kept as the prefix instead of the
    relative path.

    Issue related: https://github.com/conan-io/conan/issues/16543
    """
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile("dep", "0.1")})
    client.run("create dep/conanfile.py")
    client.run("install --requires=dep/0.1 --deployer=direct_deploy "
               "--deployer-folder=mydeploy -g PkgConfigDeps")
    content = client.load("dep.pc")
    prefix_base = client.current_folder.replace('\\', '/')
    assert f"prefix={prefix_base}/mydeploy/direct_deploy/dep" in content
    assert "libdir=${prefix}/lib" in content
    assert "includedir=${prefix}/include" in content
    assert "bindir=${prefix}/bin" in content


def test_pkg_config_deps_set_property():
    c = TestClient()
    app = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.gnu import PkgConfigDeps
        class Pkg(ConanFile):
            settings = "build_type"
            requires = "dep/0.1", "other/0.1"
            def generate(self):
                pc = PkgConfigDeps(self)
                pc.set_property("dep", "pkg_config_name", "depx264")
                pc.set_property("other::mycomp1", "nosoname", True)
                pc.generate()
            """)

    pkg_info = {"components": {"mycomp1": {"libs": ["mylib"]}}}
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_package_type("shared-library"),
            "other/conanfile.py": GenConanfile("other", "0.1").with_package_type("shared-library")
                                                              .with_package_info(pkg_info, {}),
            "app/conanfile.py": app})
    c.run("create dep")
    c.run("create other")
    c.run("install app")
    assert not os.path.exists(os.path.join(c.current_folder, "app", "dep.pc"))

    dep = c.load("app/depx264.pc")
    assert 'Name: depx264' in dep
    other = c.load("app/other.pc")
    assert 'Name: other' in other
    other_mycomp1 = c.load("app/other-mycomp1.pc")
    assert 'Name: other-mycomp1' in other_mycomp1
    assert other.split("\n")[0] == other_mycomp1.split("\n")[0]

