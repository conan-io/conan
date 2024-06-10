import json
import os
import re
import textwrap
from collections import OrderedDict

import pytest

from conan.test.utils.tools import NO_SETTINGS_PACKAGE_ID
from conan.test.utils.tools import TestClient, TestServer, GenConanfile
from conans.util.files import mkdir, save


@pytest.fixture()
def client():
    c = TestClient(default_server_user=True)
    save(c.cache.settings_path, "os: [Windows, Macos, Linux, FreeBSD]\nos_build: [Windows, Macos]")
    save(c.cache.default_profile_path, "[settings]\nos=Windows")
    return c


def test_install_reference_txt(client):
    # Test to check the "conan install <path> <reference>" command argument
    client.save({"conanfile.txt": ""})
    client.run("install .")
    assert "conanfile.txt" in client.out


def test_install_reference_error(client):
    # Test to check the "conan install <path> <reference>" command argument
    client.run("install --requires=pkg/0.1@myuser/testing --user=user --channel=testing", assert_error=True)
    assert "ERROR: Can't use --name, --version, --user or --channel arguments with --requires" in client.out
    client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    client.run("install . --channel=testing", assert_error=True)
    assert "Can't specify channel without user" in client.out


def test_install_args_error():
    c = TestClient()
    c.run("install . --requires=zlib/1.0", assert_error=True)
    assert "--requires and --tool-requires arguments are incompatible" in c.out


def test_four_subfolder_install(client):
    # https://github.com/conan-io/conan/issues/3950
    client.save({"path/to/sub/folder/conanfile.txt": ""})
    # If this doesn't, fail, all good
    client.run(" install path/to/sub/folder")


@pytest.mark.artifactory_ready
def test_install_system_requirements(client):
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        class MyPkg(ConanFile):
            def system_requirements(self):
                self.output.info("Running system requirements!!")
        """)})
    client.run(" install .")
    assert "Running system requirements!!" in client.out
    client.run("export . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run(" install --requires=pkg/0.1@lasote/testing --build='*'")
    assert "Running system requirements!!" in client.out
    client.run("upload * --confirm -r default")
    client.run('remove "*" -c')
    client.run(" install --requires=pkg/0.1@lasote/testing")
    assert "Running system requirements!!" in client.out


def test_install_transitive_pattern(client):
    # Make sure a simple conan install doesn't fire package_info() so self.package_folder breaks
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            options = {"shared": [True, False, "header"]}
            default_options = {"shared": False}
            def package_info(self):
                self.output.info("PKG OPTION: %s" % self.options.shared)
        """)})
    client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -o shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "pkg/0.1@user/testing"
            options = {"shared": [True, False, "header"]}
            default_options = {"shared": False}
            def package_info(self):
                self.output.info("PKG2 OPTION: %s" % self.options.shared)
        """)})

    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    client.run(" install --requires=pkg2/0.1@user/testing -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Priority of non-scoped options
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --requires=pkg2/0.1@user/testing -o shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of exact named option
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --requires=pkg2/0.1@user/testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of exact named option reverse
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg/*:shared=header "
               "--build=missing")
    assert "pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    client.run(" install --requires=pkg2/0.1@user/testing -o *:shared=True -o pkg/*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Prevalence of alphabetical pattern
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --requires=pkg2/0.1@user/testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of last match, even first pattern match
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o pkg2*:shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    client.run(" install --requires=pkg2/0.1@user/testing -o pkg2*:shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Prevalence and override of alphabetical pattern
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --requires=pkg2/0.1@user/testing -o *:shared=True -o pkg*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out


def test_install_package_folder(client):
    # Make sure a simple conan install doesn't fire package_info() so self.package_folder breaks
    client.save({"conanfile.py": textwrap.dedent("""\
        from conan import ConanFile
        import os
        class Pkg(ConanFile):
            def package_info(self):
                self.dummy_doesnt_exist_not_break
                self.output.info("Hello")
                self.env_info.PATH = os.path.join(self.package_folder, "bin")
        """)})
    client.run("install .")
    assert "Hello" not in client.out


def test_install_cwd(client):
    client.save({"conanfile.py": GenConanfile("hello", "0.1").with_setting("os")})
    client.run("export . --user=lasote --channel=stable")
    client.save({"conanfile.txt": "[requires]\nhello/0.1@lasote/stable"}, clean_first=True)

    client.run("install . --build=missing -s os_build=Windows")
    assert "hello/0.1@lasote/stable#a20db3358243e96aa07f654eaada1564 - Cache" in client.out


def test_install_with_profile(client):
    # Test for https://github.com/conan-io/conan/pull/2043
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "os"
            def requirements(self):
                self.output.info("PKGOS=%s" % self.settings.os)
        """)

    client.save({"conanfile.py": conanfile})
    save(os.path.join(client.cache.profiles_path, "myprofile"), "[settings]\nos=Linux")
    client.run("install . -pr=myprofile --build='*'")
    assert "PKGOS=Linux" in client.out
    mkdir(os.path.join(client.current_folder, "myprofile"))
    client.run("install . -pr=myprofile")
    save(os.path.join(client.cache.profiles_path, "myotherprofile"), "[settings]\nos=FreeBSD")
    client.run("install . -pr=myotherprofile")
    assert "PKGOS=FreeBSD" in client.out
    client.save({"myotherprofile": "Some garbage without sense [garbage]"})
    client.run("install . -pr=myotherprofile")
    assert "PKGOS=FreeBSD" in client.out
    client.run("install . -pr=./myotherprofile", assert_error=True)
    assert "Error while parsing line 0" in client.out


def test_install_with_path_errors(client):
    # Install without path param not allowed
    client.run("install", assert_error=True)
    assert "ERROR: Please specify a path" in client.out

    # Path with wrong conanfile.txt path
    client.run("install not_real_dir/conanfile.txt", assert_error=True)
    assert "Conanfile not found" in client.out


def test_install_argument_order(client):
    # https://github.com/conan-io/conan/issues/2520
    conanfile_boost = textwrap.dedent("""
        from conan import ConanFile
        class BoostConan(ConanFile):
            name = "boost"
            version = "0.1"
            options = {"shared": [True, False]}
            default_options = {"shared": True}
        """)
    conanfile = GenConanfile().with_require("boost/0.1")

    client.save({"conanfile.py": conanfile,
                 "conanfile_boost.py": conanfile_boost})
    client.run("create conanfile_boost.py ")
    client.run("install . -o boost/*:shared=True --build=missing")
    output_0 = client.out
    client.run("install . -o boost/*:shared=True --build missing")
    output_1 = client.out
    client.run("install -o boost/*:shared=True . --build missing")
    output_2 = client.out
    client.run("install -o boost/*:shared=True --build missing .")
    output_3 = client.out
    assert "ERROR" not in output_3
    assert output_0 == output_1
    assert output_1 == output_2
    assert output_2 == output_3

    client.run("install -o boost/*:shared=True --build boost . --build missing")
    output_4 = client.out
    client.run("install -o boost/*:shared=True --build missing --build boost .")
    output_5 = client.out
    assert output_4 == output_5


def test_install_anonymous(client):
    # https://github.com/conan-io/conan/issues/4871
    client.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    client.run("create . --user=lasote --channel=testing")
    client.run("upload * --confirm -r default")
    client2 = TestClient(servers=client.servers, inputs=[])
    client2.run("install --requires=pkg/0.1@lasote/testing")
    assert "pkg/0.1@lasote/testing: Package installed" in client2.out


@pytest.mark.artifactory_ready
def test_install_without_ref(client):
    client.save({"conanfile.py": GenConanfile("lib", "1.0")})
    client.run('create .')
    assert "lib/1.0: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID) in client.out

    client.run('upload lib/1.0 -c -r default')
    assert "Uploading recipe 'lib/1.0" in client.out

    client.run('remove "*" -c')

    # This fails, Conan thinks this is a path
    client.run('install lib/1.0', assert_error=True)
    fake_path = os.path.join(client.current_folder, "lib", "1.0")
    assert "Conanfile not found at {}".format(fake_path) in client.out

    # Try this syntax to upload too
    client.run('install --requires=lib/1.0@')
    client.run('upload lib/1.0 -c -r default')


@pytest.mark.artifactory_ready
def test_install_disabled_remote(client):
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("upload * --confirm -r default")
    client.run("remote disable default")
    client.run("install --requires=pkg/0.1@lasote/testing -r default", assert_error=True)
    assert "ERROR: Remote 'default' can't be found or is disabled" in client.out
    client.run("remote enable default")
    client.run("install --requires=pkg/0.1@lasote/testing -r default")
    client.run("remote disable default")
    client.run("install --requires=pkg/0.1@lasote/testing --update -r default", assert_error=True)
    assert "ERROR: Remote 'default' can't be found or is disabled" in client.out


def test_install_no_remotes(client):
    client.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    client.run("create .")
    client.run("upload * --confirm -r default")
    client.run("remove * -c")
    client.run("install --requires=pkg/0.1 -nr", assert_error=True)
    assert "ERROR: Package 'pkg/0.1' not resolved: No remote defined" in client.out
    client.run("install --requires=pkg/0.1")  # this works without issue
    client.run("install --requires=pkg/0.1 -nr")  # and now this too, pkg in cache


def test_install_skip_disabled_remote():
    client = TestClient(servers=OrderedDict({"default": TestServer(),
                                             "server2": TestServer(),
                                             "server3": TestServer()}),
                        inputs=2*["admin", "password"])
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("upload * --confirm -r default")
    client.run("upload * --confirm -r server3")
    client.run("remove * -c")
    client.run("remote disable default")
    client.run("install --requires=pkg/0.1@lasote/testing", assert_error=False)
    assert "Trying with 'default'..." not in client.out


def test_install_without_update_fail(client):
    # https://github.com/conan-io/conan/issues/9183
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=zlib --version=1.0")
    client.run("upload * --confirm -r default")
    client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0")})
    client.run("remote disable default")
    client.run("install .")
    assert "zlib/1.0: Already installed" in client.out


def test_install_version_range_reference(client):
    # https://github.com/conan-io/conan/issues/5905
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=0.1 --user=user --channel=channel")
    client.run("install --requires=pkg/[*]@user/channel")
    assert "pkg/0.1@user/channel: Already installed!" in client.out
    client.run("install --requires=pkg/[>0]@user/channel")
    assert "pkg/0.1@user/channel: Already installed!" in client.out


def test_install_error_never(client):
    client.save({"conanfile.py": GenConanfile("hello0", "0.1")})
    client.run("create .")
    client.run("install . --build never --build missing", assert_error=True)
    assert "ERROR: --build=never not compatible with other options" in client.out
    client.run("install conanfile.py --build never --build Hello", assert_error=True)
    assert "ERROR: --build=never not compatible with other options" in client.out
    client.run("install ./conanfile.py --build never --build outdated", assert_error=True)
    assert "ERROR: --build=never not compatible with other options" in client.out


def test_package_folder_available_consumer():
    """
    The package folder is not available when doing a consumer conan install "."
    We don't want to provide the package folder for the "cmake install" nor the "make install",
    as a consumer you could call the build system and pass the prefix PATH manually.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import cmake_layout
    class HelloConan(ConanFile):
        settings = "os", "arch", "build_type"
        def layout(self):
            cmake_layout(self)
        def generate(self):
            self.output.warning("Package folder is None? {}".format(self.package_folder is None))
            self.output.warning("Package folder: {}".format(self.package_folder))
    """)
    client.save({"conanfile.py": conanfile})

    # Installing it with "install ." with output folder
    client.run("install . -of=my_build")
    assert "WARN: Package folder is None? True" in client.out

    # Installing it with "install ." without output folder
    client.run("install .")
    assert "WARN: Package folder is None? True" in client.out


def test_install_multiple_requires_cli():
    """
    Test that it is possible to install multiple --requires=xxx --requires=yyy
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile()})
    c.run("create . --name=pkg1 --version=0.1")
    c.run("create . --name=pkg2 --version=0.1")

    c.run("graph info --requires=pkg1/0.1 --requires=pkg2/0.1")
    assert "pkg1/0.1" in c.out
    assert "pkg2/0.1" in c.out
    c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1")
    assert "pkg1/0.1" in c.out
    assert "pkg2/0.1" in c.out
    c.run("lock create --requires=pkg1/0.1 --requires=pkg2/0.1 --lockfile-out=conan.lock")
    lock = c.load("conan.lock")
    assert "pkg1/0.1" in lock
    assert "pkg2/0.1" in lock


def test_install_json_formatter():
    """
    Tests the ``conan install . -f json`` result
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyTest(ConanFile):
            name = "pkg"
            version = "0.2"

            def package_info(self):
                self.cpp_info.libs = ["pkg"]
                self.cpp_info.includedirs = ["path/includes/pkg", "other/include/path/pkg"]
                self.cpp_info.libdirs = ["one/lib/path/pkg"]
                self.cpp_info.defines = ["pkg_onedefinition", "pkg_twodefinition"]
                self.cpp_info.cflags = ["pkg_a_c_flag"]
                self.cpp_info.cxxflags = ["pkg_a_cxx_flag"]
                self.cpp_info.sharedlinkflags = ["pkg_shared_link_flag"]
                self.cpp_info.exelinkflags = ["pkg_exe_link_flag"]
                self.cpp_info.sysroot = "/path/to/folder/pkg"
                self.cpp_info.frameworks = ["pkg_oneframework", "pkg_twoframework"]
                self.cpp_info.system_libs = ["pkg_onesystemlib", "pkg_twosystemlib"]
                self.cpp_info.frameworkdirs = ["one/framework/path/pkg"]
                self.cpp_info.set_property("pkg_config_name", "pkg_other_name")
                self.cpp_info.set_property("pkg_config_aliases", ["pkg_alias1", "pkg_alias2"])
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "compo1")
                self.cpp_info.components["cmp1"].set_property("pkg_config_aliases", ["compo1_alias"])
                self.cpp_info.components["cmp1"].sysroot = "/another/sysroot"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.1")
                .with_require("pkg/0.2")}, clean_first=True)
    client.run("install . -f json")
    info = json.loads(client.stdout)
    nodes = info["graph"]["nodes"]
    hello_pkg_ref = 'hello/0.1'  # no revision available
    pkg_pkg_ref = 'pkg/0.2#926714b5fb0a994f47ec37e071eba1da'
    hello_cpp_info = pkg_cpp_info = None
    for _, n in nodes.items():
        ref = n["ref"]
        if ref == hello_pkg_ref:
            assert n['binary'] is None
            hello_cpp_info = n['cpp_info']
        elif ref == pkg_pkg_ref:
            assert n['binary'] == "Cache"
            pkg_cpp_info = n['cpp_info']

    hello = nodes["0"]
    assert hello["ref"] == hello_pkg_ref
    assert hello["recipe_folder"] == client.current_folder
    assert hello["build_folder"] == client.current_folder
    assert hello["generators_folder"] == client.current_folder
    assert hello["package_folder"] is None

    assert hello_cpp_info and pkg_cpp_info
    # hello/0.1 cpp_info
    assert hello_cpp_info['root']["libs"] is None
    assert len(hello_cpp_info['root']["bindirs"]) == 1
    assert len(hello_cpp_info['root']["libdirs"]) == 1
    assert hello_cpp_info['root']["sysroot"] is None
    assert hello_cpp_info['root']["properties"] is None
    # pkg/0.2 cpp_info
    # root info
    assert pkg_cpp_info['root']["libs"] == ['pkg']
    assert len(pkg_cpp_info['root']["bindirs"]) == 1
    assert len(pkg_cpp_info['root']["libdirs"]) == 1
    assert pkg_cpp_info['root']["sysroot"] == '/path/to/folder/pkg'
    assert pkg_cpp_info['root']["system_libs"] == ['pkg_onesystemlib', 'pkg_twosystemlib']
    assert pkg_cpp_info['root']['cflags'] == ['pkg_a_c_flag']
    assert pkg_cpp_info['root']['cxxflags'] == ['pkg_a_cxx_flag']
    assert pkg_cpp_info['root']['defines'] == ['pkg_onedefinition', 'pkg_twodefinition']
    assert pkg_cpp_info['root']["properties"] == {
        'pkg_config_aliases': ['pkg_alias1', 'pkg_alias2'],
        'pkg_config_name': 'pkg_other_name'}
    # component info
    assert pkg_cpp_info['cmp1']["libs"] == ['libcmp1']
    assert pkg_cpp_info['cmp1']["bindirs"][0].endswith("bin")  # Abs path /bin
    assert pkg_cpp_info['cmp1']["libdirs"][0].endswith("lib")  # Abs path /lib
    assert pkg_cpp_info['cmp1']["sysroot"] == "/another/sysroot"
    assert pkg_cpp_info['cmp1']["properties"] == {'pkg_config_aliases': ['compo1_alias'],
                                                  'pkg_config_name': 'compo1'}


def test_upload_skip_binaries_not_hit_server():
    """
    When upload_policy = "skip", no need to try to install from servers
    """
    c = TestClient(servers={"default": None})  # Broken server, will raise error if used
    conanfile = GenConanfile("pkg", "0.1").with_class_attribute('upload_policy = "skip"')
    c.save({"conanfile.py": conanfile})
    c.run("export .")
    c.run("install --requires=pkg/0.1 --build=missing")
    # This would crash if hits the server, but it doesnt
    assert "pkg/0.1: Created package" in c.out


def test_upload_skip_build_missing():
    c = TestClient(default_server_user=True)
    pkg1 = GenConanfile("pkg1", "1.0").with_class_attribute('upload_policy = "skip"')
    pkg2 = GenConanfile("pkg2", "1.0").with_requirement("pkg1/1.0", visible=False)
    pkg3 = GenConanfile("pkg3", "1.0").with_requirement("pkg2/1.0")
    c.save({"pkg1/conanfile.py": pkg1,
            "pkg2/conanfile.py": pkg2,
            "pkg3/conanfile.py": pkg3,
            })
    c.run("create pkg1")
    c.run("create pkg2")
    c.run("remove pkg1/*:* -c")  # remove binaries
    c.run("create pkg3 --build=missing")
    assert re.search(r"Skipped binaries(\s*)pkg1/1.0", c.out)


def test_upload_skip_build_compatibles():
    c = TestClient()
    pkg1 = textwrap.dedent("""\
        from conan import ConanFile
        class Pkg1(ConanFile):
            name = "pkg1"
            version = "1.0"
            settings = "build_type"
            upload_policy = "skip"
            def compatibility(self):
                if self.settings.build_type == "Debug":
                    return [{"settings": [("build_type", "Release")]}]
            """)
    pkg2 = GenConanfile("pkg2", "1.0").with_requirement("pkg1/1.0")
    pkg3 = GenConanfile("pkg3", "1.0").with_requirement("pkg2/1.0")
    c.save({"pkg1/conanfile.py": pkg1,
            "pkg2/conanfile.py": pkg2,
            "pkg3/conanfile.py": pkg3,
            })
    c.run("create pkg1 -s build_type=Release")
    pkg1id = c.created_package_id("pkg1/1.0")
    c.run("create pkg2 -s build_type=Release")
    c.run("remove pkg1/*:* -c")  # remove binaries
    c.run("create pkg3 -s build_type=Release --build=missing")
    c.assert_listed_binary({"pkg1/1.0": (pkg1id, "Build")})
    c.run("install pkg3 -s build_type=Debug --build=missing")
    c.assert_listed_binary({"pkg1/1.0": (pkg1id, "Cache")})


def test_install_json_format():
    # https://github.com/conan-io/conan/issues/14414
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyTest(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "build_type"

            def package_info(self):
                self.conf_info.define("user.myteam:myconf", "myvalue")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.run("install --requires=pkg/0.1 --format=json")
    data = json.loads(client.stdout)
    conf_info = data["graph"]["nodes"]["1"]["conf_info"]
    assert {'user.myteam:myconf': 'myvalue'} == conf_info


def test_install_json_format_not_visible():
    """
    The dependencies that are needed at built time, even if they are not visible, or not standard
    libraries (headers=False, libs=False, run=False), like for example some build assets
    So direct dependencies of a consumer package or a package that needs to be built cannot be
    skipped
    """
    c = TestClient()
    dep = GenConanfile("dep", "0.1").with_package_file("somefile.txt", "contents!!!")
    app = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load

        class Pkg(ConanFile):
            settings = "os", "arch", "build_type"
            name="pkg"
            version="0.0.1"

            def requirements(self):
                self.requires("dep/0.1", visible=False, headers=False, libs=False, run=False)

            def build(self):
                p = os.path.join(self.dependencies["dep"].package_folder, "somefile.txt")
                c = load(self, p)
                self.output.info(f"LOADED! {c}")
        """)
    c.save({"dep/conanfile.py": dep,
            "app/conanfile.py": app})
    c.run("export-pkg dep")
    c.run("install app --format=json")
    c.assert_listed_binary({"dep/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")})
    data = json.loads(c.stdout)
    pkg_folder = data["graph"]["nodes"]["1"]["package_folder"]
    assert pkg_folder is not None

    c.run("create app")
    assert "pkg/0.0.1: LOADED! contents!!!" in c.out
