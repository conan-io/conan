import re
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


def test_private_skip():
    # app -> pkg -(private)-> dep
    client = TestClient(light=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0", visible=False)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove dep/1.0:* -c")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    client.run("create . --name=app --version=1.0 -v")
    client.assert_listed_binary({"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})


def test_private_no_skip():
    # app -> pkg -(private)-> dep
    client = TestClient(light=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0", visible=False)})
    client.run("create . --name=pkg --version=1.0")

    # But if we want to build pkg, no skip
    client.run("create . --name=app --version=1.0 --build=app/* --build=pkg/*")
    client.assert_listed_binary({"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})

    client.run("remove dep/1.0:* -c")  # Dep binary is removed not used at all
    client.run("create . --name=app --version=1.0 --build=app/* --build=pkg/*", assert_error=True)
    client.assert_listed_binary({"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Missing")})


def test_consumer_no_skip():
    # app -(private)-> pkg -> dep
    client = TestClient(light=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requires("dep/1.0")})
    client.run("create . --name=pkg --version=1.0")
    package_id = client.created_package_id("pkg/1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("pkg/1.0", visible=False)})

    client.run("install . ")

    client.assert_listed_binary({f"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    client.assert_listed_binary({f"pkg/1.0": (package_id, "Cache")})


def test_shared_link_static_skip():
    # app -> pkg (shared) -> dep (static)
    client = TestClient(light=True)
    client.save({"conanfile.py": GenConanfile().with_shared_option(False)})
    client.run("create . --name=dep --version=1.0")
    package_id = client.created_package_id("dep/1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0").
                with_shared_option(True)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove dep/1.0:* -c")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    client.run("create . --name=app --version=1.0 -v")
    client.assert_listed_binary({"dep/1.0": (package_id, "Skip")})


def test_test_requires():
    # Using a test_requires can be skipped if it is not necessary to build its consumer
    # app -> pkg (static) -(test_requires)-> gtest (static)
    client = TestClient(light=True)
    client.save({"conanfile.py": GenConanfile().with_shared_option(False)})
    client.run("create . --name=gtest --version=1.0")
    package_id = client.created_package_id("gtest/1.0")
    client.save({"conanfile.py": GenConanfile().with_test_requires("gtest/1.0").
                with_shared_option(False)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove gtest/1.0:* -c")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    # Checking list of skipped binaries
    client.run("create . --name=app --version=1.0")
    assert re.search(r"Skipped binaries(\s*)gtest/1.0", client.out)
    # Showing the complete information about the skipped binary
    client.run("create . --name=app --version=1.0 -v")
    client.assert_listed_binary({"gtest/1.0": (package_id, "Skip")}, test=True)


def test_build_scripts_no_skip():
    c = TestClient(light=True)
    c.save({"scripts/conanfile.py": GenConanfile("script", "0.1").with_package_type("build-scripts"),
            "app/conanfile.py": GenConanfile().with_tool_requires("script/0.1")})
    c.run("create scripts")
    c.assert_listed_binary({"script/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Build")},
                           build=True)
    c.run("install app")
    c.assert_listed_binary({"script/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")},
                           build=True)


def test_list_skip_printing():
    """ make sure that when a package is required in the graph, it is not marked as SKIP, just
    because some other part of the graph is skipping it. In this case, a tool_require might be
    necessary for some packages building from soures, but not for others
    """
    c = TestClient(light=True)
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_tool_requires("tool/0.1"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1")
                                                            .with_tool_requires("tool/0.1"),
            "app/conanfile.py": GenConanfile().with_requires("pkgb/0.1")})
    c.run("create tool")
    c.run("create pkga")
    c.run("create pkgb")
    c.run("remove pkga:* -c")
    c.run("install app --build=missing")
    c.assert_listed_binary({"tool/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")},
                           build=True)


def test_conf_skip():
    client = TestClient(light=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=maths --version=1.0")
    client.run("create . --name=ai --version=1.0")

    client.save({"conanfile.py": GenConanfile().with_requirement("maths/1.0", visible=False)})
    client.run("create . --name=liba --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("ai/1.0", visible=False)})
    client.run("create . --name=libb --version=1.0")

    client.save({"conanfile.py": GenConanfile().with_requires("liba/1.0", "libb/1.0")})
    client.run("create . --name=app --version=0.0 -v")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})

    client.run("create . --name=app --version=1.0 -v -c *:tools.graph:skip_binaries=False")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})

    client.run("create . --name=app --version=2.0 -v -c maths/*:tools.graph:skip_binaries=False")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})

    client.run("create . --name=app --version=3.0 -v -c *:tools.graph:skip_binaries=True")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})


def test_skipped_intermediate_header():
    # app -> libc/0.1 (static) -> libb0.1 (header) -> liba0.1 (static)
    # This libb0.1 cannot be skipped because it is necessary its lib-config.cmake for transitivity
    c = TestClient()
    c.save({"liba/conanfile.py": GenConanfile("liba", "0.1").with_package_type("static-library")
                                                            .with_package_info(cpp_info={"libs":
                                                                                         ["liba"]},
                                                                               env_info={}),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_package_type("header-library")
                                                            .with_requires("liba/0.1"),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_package_type("static-library")
                                                            .with_requires("libb/0.1"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requires("libc/0.1")
                                                          .with_settings("build_type")})
    c.run("create liba")
    c.run("create libb")
    c.run("create libc")
    c.run("install app -g CMakeDeps")
    c.assert_listed_binary({"liba/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache"),
                            "libb/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache"),
                            "libc/0.1": ("0f9f8919daed27aacd18c33199957e8882a87fd7", "Cache")})
    libc_data = c.load("app/libc-release-data.cmake")
    assert "list(APPEND libc_FIND_DEPENDENCY_NAMES libb)" in libc_data
    libb_data = c.load("app/libb-release-data.cmake")
    # libb brings no headers nor libraries
    assert "set(libb_INCLUDE_DIRS_RELEASE )" in libb_data
    assert "set(libb_LIBS_RELEASE )" in libb_data
    liba_data = c.load("app/liba-release-data.cmake")
    # liba brings only libraries
    assert "set(liba_INCLUDE_DIRS_RELEASE )" in liba_data
    assert "set(liba_LIBS_RELEASE liba)" in liba_data


def test_skip_visible_build():
    # https://github.com/conan-io/conan/issues/15346
    c = TestClient(light=True)
    c.save({"liba/conanfile.py": GenConanfile("liba", "0.1"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_requirement("liba/0.1",
                                                                              build=True),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_requirement("libb/0.1",
                                                                              visible=False),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requires("libc/0.1")})
    c.run("create liba")
    c.run("create libb")
    c.run("create libc")
    c.run("install app --format=json")
    assert re.search(r"Skipped binaries(\s*)libb/0.1, liba/0.1", c.out)


def test_skip_tool_requires_context():
    c = TestClient()
    cmake = textwrap.dedent("""
        from conan import ConanFile
        class CMake(ConanFile):
            name = "cmake"
            version = "1.0"
            def package_info(self):
                self.buildenv_info.define("MYVAR", "MYVALUE")
            """)
    gtest = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import load
        class gtest(ConanFile):
            name = "gtest"
            version = "1.0"
            settings = "os"
            package_type = "static-library"
            def build(self):
                env = load(self, "conanbuildenv.sh")
                self.output.info(f"MYENV: {env}")
        """)
    c.save({"cmake/conanfile.py": cmake,
            "gtest/conanfile.py": gtest,
            "lib/conanfile.py": GenConanfile("lib", "1.0").with_package_type("static-library")
                                                          .with_test_requires("gtest/1.0"),
            "app/conanfile.py": GenConanfile("app", "1.0").with_settings("os")
                                                          .with_requires("lib/1.0"),
            "profile": "[tool_requires]\ncmake/[>=1.0]"})

    c.run("create cmake")
    c.run("create gtest -s:a os=Linux")
    c.run("create lib -s:a os=Linux")

    c.run("remove gtest:* -c")
    c.run("install app -s:a os=Linux -pr=profile -c=tools.graph:skip_binaries=False --build=missing")
    assert 'export MYVAR="MYVALUE"' in c.out
    assert "gtest/1.0: Package '9a4eb3c8701508aa9458b1a73d0633783ecc2270' built" in c.out


def test_skip_intermediate_header():
    # https://github.com/conan-io/conan/issues/16402
    # Libb cannot be skipped in any case, because there is a link order libc->liba necessary
    # app -> libc/0.1 (static) -> libb0.1 (header) -> liba0.1 (static)
    #  \------------------------------------------------/
    # libb
    c = TestClient(light=True)
    c.save({"liba/conanfile.py": GenConanfile("liba", "0.1").with_package_type("static-library"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_requirement("liba/0.1")
                                                            .with_package_type("header-library"),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_requirement("libb/0.1")
                                                            .with_package_type("static-library"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_package_type("application")
                                                          .with_requires("libc/0.1", "liba/0.1")})
    c.run("create liba")
    c.run("create libb")
    c.run("create libc")
    c.run("install app")
    assert "Skipped binaries" not in c.out
    assert "libb/0.1: Already installed!" in c.out
    assert "liba/0.1: Already installed!" in c.out
    assert "libc/0.1: Already installed!" in c.out


def test_skip_intermediate_static():
    # https://github.com/conan-io/conan/issues/16402
    # In this case, libb can be completely skipped, because there is no linkage relationship at all
    # app -> libc/0.1 (shared) -> libb0.1 (static) -> liba0.1 (static)
    #  \------------------------------------------------/
    # libb
    c = TestClient(light=True)
    c.save({"liba/conanfile.py": GenConanfile("liba", "0.1").with_package_type("static-library"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_requirement("liba/0.1")
                                                            .with_package_type("static-library"),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_requirement("libb/0.1")
                                                            .with_package_type("shared-library"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_package_type("application")
                                                          .with_requires("libc/0.1", "liba/0.1")})
    c.run("create liba")
    c.run("create libb")
    c.run("create libc")
    c.run("remove libb:* -c")  # binary not necessary, can be skipped
    c.run("install app")
    assert re.search(r"Skipped binaries(\s*)libb/0.1", c.out)
    assert "libb/0.1: Already installed!" not in c.out
    assert "liba/0.1: Already installed!" in c.out
    assert "libc/0.1: Already installed!" in c.out


def test_skip_intermediate_static_complex():
    # https://github.com/conan-io/conan/issues/16402
    #  /----- libh(static)--libi(header)---libj(header)----------\
    # app -> libe(shared)->libd(static) -> libc(static) -> libb(static) -> liba(static)
    #  \---------libf(static) --libg(header)---------------------------------/
    # libd and libc can be skipped
    c = TestClient(light=True)
    c.save({"liba/conanfile.py": GenConanfile("liba", "0.1").with_package_type("static-library"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_requirement("liba/0.1")
                                                            .with_package_type("static-library"),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_requirement("libb/0.1")
                                                            .with_package_type("static-library"),
            "libd/conanfile.py": GenConanfile("libd", "0.1").with_requirement("libc/0.1")
                                                            .with_package_type("static-library"),
            "libe/conanfile.py": GenConanfile("libe", "0.1").with_requirement("libd/0.1")
                                                            .with_package_type("shared-library"),
            "libg/conanfile.py": GenConanfile("libg", "0.1").with_requirement("liba/0.1")
                                                            .with_package_type("header-library"),
            "libf/conanfile.py": GenConanfile("libf", "0.1").with_requirement("libg/0.1")
                                                            .with_package_type("static-library"),
            "libj/conanfile.py": GenConanfile("libj", "0.1").with_requirement("libb/0.1")
                                                            .with_package_type("header-library"),
            "libi/conanfile.py": GenConanfile("libi", "0.1").with_requirement("libj/0.1")
                                                            .with_package_type("header-library"),
            "libh/conanfile.py": GenConanfile("libh", "0.1").with_requirement("libi/0.1")
                                                            .with_package_type("static-library"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_package_type("application")
                                                          .with_requires("libh/0.1", "libe/0.1",
                                                                         "libf/0.1")
            })
    for lib in ("a", "b", "c", "d", "e", "j", "i", "h", "g", "f"):
        c.run(f"create lib{lib}")

    c.run("remove libd:* -c")  # binary not necessary, can be skipped
    c.run("remove libc:* -c")  # binary not necessary, can be skipped
    c.run("install app")
    assert re.search(r"Skipped binaries(\s*)libc/0.1, libd/0.1", c.out)
    assert "libd/0.1: Already installed!" not in c.out
    assert "libc/0.1: Already installed!" not in c.out
    for lib in ("a", "b", "e", "f", "g", "h", "i", "j"):
        assert f"lib{lib}/0.1: Already installed!" in c.out
    for lib in ("c", "d"):
        assert f"lib{lib}/0.1: Already installed!" not in c.out
