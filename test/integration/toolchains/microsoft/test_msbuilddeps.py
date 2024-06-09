import glob
import os
import platform
import textwrap
from xml.dom import minidom

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize(
    "arch,exp_platform",
    [
        ("x86", "Win32"),
        ("x86_64", "x64"),
        ("armv7", "ARM"),
        ("armv8", "ARM64"),
    ],
)
def test_msbuilddeps_maps_architecture_to_platform(arch, exp_platform):
    client = TestClient()
    client.run("new msbuild_lib -d name=hello -d version=0.1")
    client.run(f"install . -g MSBuildDeps -s arch={arch} -pr:b=default")
    toolchain = client.load(os.path.join("conan", "conantoolchain.props"))
    expected_import = f"""<Import Condition="'$(Configuration)' == 'Release' And '$(Platform)' == '{exp_platform}'" Project="conantoolchain_release_{exp_platform.lower()}.props"/>"""
    assert expected_import in toolchain


def test_msbuilddeps_format_names():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "pkg.name-more+"
            version = "1.0"

            def package_info(self):
                self.cpp_info.components["libmpdecimal++"].libs = ["libmp++"]
                self.cpp_info.components["mycomp.some-comp+"].libs = ["mylib"]
                self.cpp_info.components["libmpdecimal++"].requires = ["mycomp.some-comp+"]
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create . -s arch=x86_64")
    # Issue: https://github.com/conan-io/conan/issues/11822
    c.run("install --require=pkg.name-more+/1.0@ -g MSBuildDeps -s build_type=Release -s arch=x86_64")
    # Checking that MSBuildDeps builds correctly the XML file
    # loading all .props and xml parse them to check no errors
    pkg_more = c.load("conan_pkg_name-more_.props")
    assert "$(conan_pkg_name-more__libmpdecimal___props_imported)" in pkg_more
    assert "$(conan_pkg_name-more__mycomp_some-comp__props_imported)" in pkg_more

    some_comp = c.load("conan_pkg_name-more__mycomp_some-comp_.props")
    assert "<conan_pkg_name-more__mycomp_some-comp__props_imported>" in some_comp

    libmpdecimal = c.load("conan_pkg_name-more__libmpdecimal__.props")
    assert "<conan_pkg_name-more__libmpdecimal___props_imported>" in libmpdecimal

    libmpdecimal_release = c.load("conan_pkg_name-more__libmpdecimal___release_x64.props")
    assert "$(conan_pkg_name-more__mycomp_some-comp__props_imported)" in libmpdecimal_release

    counter = 0
    for f in os.listdir(c.current_folder):
        if f.endswith(".props"):
            content = c.load(f)
            minidom.parseString(content)
            counter += 1
    assert counter == 8


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
class TestMSBuildDepsSkips:
    # https://github.com/conan-io/conan/issues/15624
    def test_msbuilddeps_skipped_deps(self):
        c = TestClient()
        c.save({"liba/conanfile.py": GenConanfile("liba", "0.1").with_package_type("header-library"),
                "libb/conanfile.py": GenConanfile("libb", "0.1").with_package_type("static-library")
                                                                .with_requires("liba/0.1"),
                "app/conanfile.py": GenConanfile().with_requires("libb/0.1")
                                                  .with_settings("arch", "build_type")})
        c.run("create liba")
        c.run("create libb")
        c.run("install app -g MSBuildDeps")
        assert not os.path.exists(os.path.join(c.current_folder, "app", "conan_liba.props"))
        assert os.path.exists(os.path.join(c.current_folder, "app", "conan_libb.props"))
        libb = c.load("app/conan_libb.props")
        assert "conan_liba" not in libb
        libb = c.load("app/conan_libb_release_x64.props")
        assert "conan_liba" not in libb
        libb = c.load("app/conan_libb_vars_release_x64.props")
        assert "conan_liba" not in libb

    def test_msbuilddeps_skipped_deps_components(self):
        c = TestClient()
        libb = textwrap.dedent("""
            from conan import ConanFile
            class Libb(ConanFile):
                name = "libb"
                version = "0.1"
                package_type = "static-library"
                requires = "liba/0.1"
                def package_info(self):
                    self.cpp_info.components["mycomp"].libs = ["mycomplib"]
                    self.cpp_info.components["mycomp"].requires = ["liba::liba"]
            """)

        c.save({"liba/conanfile.py": GenConanfile("liba", "0.1").with_package_type("header-library"),
                "libb/conanfile.py": libb,
                "app/conanfile.py": GenConanfile().with_requires("libb/0.1")
                                                  .with_settings("arch", "build_type")})
        c.run("create liba")
        c.run("create libb")
        c.run("install app -g MSBuildDeps")
        assert not os.path.exists(os.path.join(c.current_folder, "app", "conan_liba.props"))
        assert os.path.exists(os.path.join(c.current_folder, "app", "conan_libb.props"))
        libb = c.load("app/conan_libb.props")
        assert "conan_liba" not in libb
        libb = c.load("app/conan_libb_mycomp.props")
        assert "conan_liba" not in libb
        libb = c.load("app/conan_libb_mycomp_release_x64.props")
        assert "conan_liba" not in libb
        libb = c.load("app/conan_libb_mycomp_vars_release_x64.props")
        assert "conan_liba" not in libb


@pytest.mark.skipif(platform.system() != "Windows", reason="MSBuildDeps broken with POSIX paths")
@pytest.mark.parametrize("withdepl", [False, True])
def test_msbuilddeps_relocatable(withdepl):
    c = TestClient()
    c.save({
        "libh/conanfile.py": GenConanfile("libh", "0.1")
            .with_package_type("header-library"),
        "libs/conanfile.py": GenConanfile("libs", "0.2")
            .with_package_type("static-library")
            .with_requires("libh/0.1"),
        "libd/conanfile.py": GenConanfile("libd", "0.3")
            .with_package_type("shared-library"),
        "app/conanfile.py": GenConanfile()
            .with_requires("libh/0.1")
            .with_requires("libs/0.2")
            .with_requires("libd/0.3")
            .with_settings("arch", "build_type"),
    })

    c.run("create libh")
    c.run("create libs")
    c.run("create libd")
    c.run("install app -g MSBuildDeps" + (" -d full_deploy" if withdepl else ""))

    for dep in ["libh", "libs", "libd"]:
        text = c.load(f"app/conan_{dep}_vars_release_x64.props")
        marker = f"Conan{dep}RootFolder"
        value = text.split(f"<{marker}>")[1].split(f"</{marker}>")[0]
        if withdepl:
            # path should be relative, since artifacts are moved along with project
            prefix = '$(MSBuildThisFileDirectory)/'
            assert value.startswith(prefix)
            tail = value[len(prefix):]
            assert not os.path.isabs(tail)
        else:
            # path should be absolute, since conan cache does not move with project
            assert os.path.isabs(value)
            assert '$(' not in value

    if withdepl:
        # extra checks: no absolute paths allowed anywhere in props
        propsfiles = glob.glob(os.path.join(c.current_folder, "app/*.props"))
        assert len(propsfiles) > 0
        for fn in propsfiles:
            text = c.load(fn)
            text = text.replace('\\', '/')
            dir = c.current_folder.replace('\\', '/')
            assert dir not in text
