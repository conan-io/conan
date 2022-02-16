import os
import textwrap
from collections import OrderedDict

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID
from conans.test.utils.tools import TestClient, TestServer, GenConanfile
from conans.util.files import mkdir, rmdir, save


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
    client.run("install --reference=pkg/0.1@myuser/testing --user=user --channel=testing", assert_error=True)
    assert "ERROR: Can't use --name, --version, --user or --channel arguments with --reference" in client.out


def test_four_subfolder_install(client):
    # https://github.com/conan-io/conan/issues/3950
    client.save({"path/to/sub/folder/conanfile.txt": ""})
    # If this doesn't, fail, all good
    client.run(" install path/to/sub/folder")


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
    client.run(" install --reference=pkg/0.1@lasote/testing --build")
    assert "Running system requirements!!" in client.out
    client.run("upload * --confirm -r default")
    client.run('remove "*" -f')
    client.run(" install --reference=pkg/0.1@lasote/testing")
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
    client.run(" install --reference=pkg2/0.1@user/testing -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Priority of non-scoped options
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --reference=pkg2/0.1@user/testing -o shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of exact named option
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --reference=pkg2/0.1@user/testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of exact named option reverse
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg/*:shared=header "
               "--build=missing")
    assert "pkg/0.1@user/testing: Calling build()" in client.out
    assert "pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    client.run(" install --reference=pkg2/0.1@user/testing -o *:shared=True -o pkg/*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Prevalence of alphabetical pattern
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --reference=pkg2/0.1@user/testing -o *:shared=True -o pkg2*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of last match, even first pattern match
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o pkg2*:shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    client.run(" install --reference=pkg2/0.1@user/testing -o pkg2*:shared=header -o *:shared=True")
    assert "pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Prevalence and override of alphabetical pattern
    client.run("create . --name=pkg2 --version=0.1 --user=user --channel=testing -o *:shared=True -o pkg*:shared=header")
    assert "pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install --reference=pkg2/0.1@user/testing -o *:shared=True -o pkg*:shared=header")
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
    client.run("install . -pr=myprofile --build")
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
    assert "ERROR: Please specify at least a path to a conanfile or a valid reference." in client.out

    # Path with wrong conanfile.txt path
    client.run("install not_real_dir/conanfile.txt", assert_error=True)
    assert "Conanfile not found" in client.out


@pytest.mark.xfail(reason="cache2.0: TODO: check this case for new cache")
def test_install_broken_reference(client):
    client.save({"conanfile.py": GenConanfile()})
    client.run("export . --name=hello --version=0.1 --user=lasote --channel=stable")
    client.run("remote add_ref hello/0.1@lasote/stable default")
    ref = RecipeReference.loads("hello/0.1@lasote/stable")
    # Because the folder is removed, the metadata is removed and the
    # origin remote is lost
    rmdir(os.path.join(client.get_latest_ref_layout(ref).base_folder()))
    client.run("install --reference=hello/0.1@lasote/stable", assert_error=True)
    assert "Unable to find 'hello/0.1@lasote/stable' in remotes" in client.out

    # If it was associated, it has to be desasociated
    client.run("remote remove_ref hello/0.1@lasote/stable")
    client.run("install --reference=hello/0.1@lasote/stable", assert_error=True)
    assert "Unable to find 'hello/0.1@lasote/stable' in remotes" in client.out


@pytest.mark.xfail(reason="cache2.0: outputs building will never be the same because the uuid "
                          "of the folders")
def test_install_argument_order(client):
    # https://github.com/conan-io/conan/issues/2520
    conanfile_boost = textwrap.dedent("""
        from conan import ConanFile
        class BoostConan(ConanFile):
            name = "boost"
            version = "0.1"
            options = {"shared": [True, False]}
            default_options = "shared=True"
        """)
    conanfile = GenConanfile().with_require("boost/0.1@conan/stable")

    client.save({"conanfile.py": conanfile,
                 "conanfile_boost.py": conanfile_boost})
    client.run("create conanfile_boost.py conan/stable")
    client.run("install . -o boost/*:shared=True --build=missing")
    output_0 = "%s" % client.out
    client.run("install . -o boost/*:shared=True --build missing")
    output_1 = "%s" % client.out
    client.run("install -o boost/*:shared=True . --build missing")
    output_2 = "%s" % client.out
    client.run("install -o boost/*:shared=True --build missing .")
    output_3 = "%s" % client.out
    assert "ERROR" not in output_3
    assert output_0 == output_1
    assert output_1 == output_2
    assert output_2 == output_3

    client.run("install -o boost/*:shared=True --build boost . --build missing")
    output_4 = "%s" % client.out
    client.run("install -o boost/*:shared=True --build missing --build boost .")
    output_5 = "%s" % client.out
    assert output_4 == output_5


def test_install_anonymous(client):
    # https://github.com/conan-io/conan/issues/4871
    client.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    client.run("create . --user=lasote --channel=testing")
    client.run("upload * --confirm -r default")
    client2 = TestClient(servers=client.servers, inputs=[])
    client2.run("install --reference=pkg/0.1@lasote/testing")
    assert "pkg/0.1@lasote/testing: Package installed" in client2.out


def test_install_without_ref(client):
    client.save({"conanfile.py": GenConanfile("lib", "1.0")})
    client.run('create .')
    assert "lib/1.0: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID) in client.out

    client.run('upload lib/1.0 -c -r default')
    assert "Uploading lib/1.0" in client.out

    client.run('remove "*" -f')

    # This fails, Conan thinks this is a path
    client.run('install lib/1.0', assert_error=True)
    fake_path = os.path.join(client.current_folder, "lib", "1.0")
    assert "Conanfile not found at {}".format(fake_path) in client.out

    # Try this syntax to upload too
    client.run('install --reference=lib/1.0@')
    client.run('upload lib/1.0 -c -r default')


def test_install_disabled_remote(client):
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("upload * --confirm -r default")
    client.run("remote disable default")
    client.run("install --reference=pkg/0.1@lasote/testing -r default", assert_error=True)
    assert "Remote 'default' is disabled" in client.out
    client.run("remote enable default")
    client.run("install --reference=pkg/0.1@lasote/testing -r default")
    client.run("remote disable default")
    client.run("install --reference=pkg/0.1@lasote/testing --update -r default", assert_error=True)
    assert "Remote 'default' is disabled" in client.out


def test_install_skip_disabled_remote():
    client = TestClient(servers=OrderedDict({"default": TestServer(),
                                             "server2": TestServer(),
                                             "server3": TestServer()}),
                        inputs=2*["admin", "password"])
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("upload * --confirm -r default")
    client.run("upload * --confirm -r server3")
    client.run("remove * -f")
    client.run("remote disable default")
    client.run("install --reference=pkg/0.1@lasote/testing", assert_error=False)
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
    client.run("install --reference=pkg/[*]@user/channel")
    assert "pkg/0.1@user/channel: Already installed!" in client.out
    client.run("install --reference=pkg/[>0]@user/channel")
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


class TestCliOverride:

    def test_install_cli_override(self, client):
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=zlib --version=1.0")
        client.run("create . --name=zlib --version=2.0")
        client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0")})
        client.run("install . --require-override=zlib/2.0")
        assert "zlib/2.0: Already installed" in client.out

    def test_install_cli_override_in_conanfile_txt(self, client):
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=zlib --version=1.0")
        client.run("create . --name=zlib --version=2.0")
        client.save({"conanfile.txt": textwrap.dedent("""\
        [requires]
        zlib/1.0
        """)}, clean_first=True)
        client.run("install . --require-override=zlib/2.0")
        assert "zlib/2.0: Already installed" in client.out

    def test_install_ref_cli_override(self, client):
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=zlib --version=1.0")
        client.run("create . --name=zlib --version=1.1")
        client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0")})
        client.run("create . --name=pkg --version=1.0")
        client.run("install --reference=pkg/1.0@ --require-override=zlib/1.1")
        assert "zlib/1.1: Already installed" in client.out

    def test_create_cli_override(self, client):
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=zlib --version=1.0")
        client.run("create . --name=zlib --version=2.0")
        client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . --name=pkg --version=0.1 --require-override=zlib/2.0")
        assert "zlib/2.0: Already installed" in client.out
