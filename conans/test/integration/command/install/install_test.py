import os
import textwrap
from collections import OrderedDict

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID
from conans.test.utils.tools import TestClient, TestServer, GenConanfile
from conans.util.files import mkdir, rmdir, save


@pytest.fixture()
def client():
    c = TestClient(default_server_user=True)
    save(c.cache.settings_path, "os: [Windows, Macos, Linux, FreeBSD]\nos_build: [Windows, Macos]")
    save(c.cache.default_profile_path, "[settings]\nos=Windows")
    return c


def test_not_found_package_dirty_cache(client):
    # Conan does a lock on the cache, and even if the package doesn't exist
    # left a trailing folder with the filelocks. This test checks
    # it will be cleared
    client.save({"conanfile.py": GenConanfile("Hello", "0.1")})
    client.run("create . lasote/testing")
    client.run("upload * --all --confirm")
    client.run('remove "*" -f')
    client.run(" install hello/0.1@lasote/testing", assert_error=True)
    assert "Unable to find 'hello/0.1@lasote/testing'" in client.out
    # This used to fail in Windows, because of the trailing lock
    client.run("remove * -f")
    client.run(" install Hello/0.1@lasote/testing")


def test_install_reference_txt(client):
    # Test to check the "conan install <path> <reference>" command argument
    client.save({"conanfile.txt": ""})
    client.run("info .")
    assert "conanfile.txt" in str(client.out).splitlines()


def test_install_reference_error(client):
    # Test to check the "conan install <path> <reference>" command argument
    client.run("install Pkg/0.1@myuser/testing user/testing", assert_error=True)
    assert "ERROR: A full reference was provided as first argument" in client.out


def test_install_reference(client):
    # Test to check the "conan install <path> <reference>" command argument
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            def build(self):
                self.output.info("REF: %s, %s, %s, %s"
                                 % (self.name, self.version, self.user, self.channel))
        """)
    client.save({"conanfile.py": conanfile})
    client.run(" install . Pkg/0.1@myuser/testing")
    client.run(" info .")
    assert "Pkg/0.1@myuser/testing" in client.out
    client.run("build .")
    assert "REF: Pkg, 0.1, myuser, testing" in client.out

    # Trying with partial name
    conanfile = conanfile + "    name = 'Other'\n"
    client.save({"conanfile.py": conanfile})
    # passing the wrong package name raises
    client.run(" install . Pkg/0.1@myuser/testing", assert_error=True)
    assert "ERROR: Package recipe with name Pkg!=Other" in client.out
    # Partial reference works
    client.run(" install . 0.1@myuser/testing")
    client.run("build .")
    assert "REF: Other, 0.1, myuser, testing" in client.out
    # And also full reference matching
    client.run(" install . Other/0.1@myuser/testing")
    client.run("build .")
    assert "REF: Other, 0.1, myuser, testing" in client.out

    # Trying with partial name and version
    conanfile = conanfile + "    version = '0.2'\n"
    client.save({"conanfile.py": conanfile})
    # passing the wrong package name raises
    client.run(" install . Other/0.1@myuser/testing", assert_error=True)
    assert "ERROR: Package recipe with version 0.1!=0.2" in client.out
    # Partial reference works
    client.run(" install . myuser/testing")
    client.run("build .")
    assert "REF: Other, 0.2, myuser, testing" in client.out
    # And also full reference matching
    client.run(" install . Other/0.2@myuser/testing")
    client.run("build .")
    assert "REF: Other, 0.2, myuser, testing" in client.out


def test_four_subfolder_install(client):
    # https://github.com/conan-io/conan/issues/3950
    client.save({"path/to/sub/folder/conanfile.txt": ""})
    # If this doesn't, fail, all good
    client.run(" install path/to/sub/folder")


def test_install_system_requirements(client):
    client.save({"conanfile.py": textwrap.dedent("""
        from conans import ConanFile
        class MyPkg(ConanFile):
            def system_requirements(self):
                self.output.info("Running system requirements!!")
        """)})
    client.run(" install .")
    assert "Running system requirements!!" in client.out
    client.run("export . Pkg/0.1@lasote/testing")
    client.run(" install Pkg/0.1@lasote/testing --build")
    assert "Running system requirements!!" in client.out
    client.run("upload * --all --confirm")
    client.run('remove "*" -f')
    client.run(" install Pkg/0.1@lasote/testing")
    assert "Running system requirements!!" in client.out


def test_install_transitive_pattern(client):
    # Make sure a simple conan install doesn't fire package_info() so self.package_folder breaks
    client.save({"conanfile.py": textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            options = {"shared": [True, False, "header"]}
            default_options = "shared=False"
            def package_info(self):
                self.output.info("PKG OPTION: %s" % self.options.shared)
        """)})
    client.run("create . Pkg/0.1@user/testing -o shared=True")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    client.save({"conanfile.py": textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "Pkg/0.1@user/testing"
            options = {"shared": [True, False, "header"]}
            default_options = "shared=False"
            def package_info(self):
                self.output.info("PKG2 OPTION: %s" % self.options.shared)
        """)})

    client.run("create . Pkg2/0.1@user/testing -o *:shared=True")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    client.run(" install Pkg2/0.1@user/testing -o *:shared=True")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Priority of non-scoped options
    client.run("create . Pkg2/0.1@user/testing -o shared=header -o *:shared=True")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install Pkg2/0.1@user/testing -o shared=header -o *:shared=True")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of exact named option
    client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg2:shared=header")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install Pkg2/0.1@user/testing -o *:shared=True -o Pkg2:shared=header")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of exact named option reverse
    client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg:shared=header "
               "--build=missing")
    assert "Pkg/0.1@user/testing: Calling build()" in client.out
    assert "Pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    client.run(" install Pkg2/0.1@user/testing -o *:shared=True -o Pkg:shared=header")
    assert "Pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: True" in client.out
    # Prevalence of alphabetical pattern
    client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg2*:shared=header")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install Pkg2/0.1@user/testing -o *:shared=True -o Pkg2*:shared=header")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence of alphabetical pattern, opposite order
    client.run("create . Pkg2/0.1@user/testing -o Pkg2*:shared=header -o *:shared=True")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install Pkg2/0.1@user/testing -o Pkg2*:shared=header -o *:shared=True")
    assert "Pkg/0.1@user/testing: PKG OPTION: True" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    # Prevalence and override of alphabetical pattern
    client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg*:shared=header")
    assert "Pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out
    client.run(" install Pkg2/0.1@user/testing -o *:shared=True -o Pkg*:shared=header")
    assert "Pkg/0.1@user/testing: PKG OPTION: header" in client.out
    assert "Pkg2/0.1@user/testing: PKG2 OPTION: header" in client.out


def test_install_package_folder(client):
    # Make sure a simple conan install doesn't fire package_info() so self.package_folder breaks
    client.save({"conanfile.py": textwrap.dedent("""\
        from conans import ConanFile
        import os
        class Pkg(ConanFile):
            def package_info(self):
                self.dummy_doesnt_exist_not_break
                self.output.info("Hello")
                self.env_info.PATH = os.path.join(self.package_folder, "bin")
        """)})
    client.run(" install .")
    assert "Hello" not in client.out
    assert "conanfile.py: Generated conaninfo.txt" in client.out


def test_install_cwd(client):
    client.save({"conanfile.py": GenConanfile("Hello", "0.1").with_setting("os")})
    client.run("export . lasote/stable")
    client.save({"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}, clean_first=True)

    client.run("install . --build=missing -s os_build=Windows --install-folder=win_dir")
    assert "Hello/0.1@lasote/stable from local cache" in client.out
    client.run("install . --build=missing -s os=Macos -s os_build=Macos "
               "--install-folder=os_dir")
    conaninfo = client.load("win_dir/conaninfo.txt")
    assert "os=Windows" in conaninfo
    assert "os=Macos" not in conaninfo
    conaninfo = client.load("os_dir/conaninfo.txt")
    assert "os=Windows" not in conaninfo
    assert "os=Macos" in conaninfo


def test_install_reference_not_conanbuildinfo(client):
    client.save({"conanfile.py": GenConanfile("Hello", "0.1").with_setting("os")})
    client.run("create . conan/stable")
    client.save({}, clean_first=True)
    client.run("install Hello/0.1@conan/stable")
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildinfo.txt"))


def test_install_with_profile(client):
    # Test for https://github.com/conan-io/conan/pull/2043
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os"
            def requirements(self):
                self.output.info("PKGOS=%s" % self.settings.os)
        """)

    client.save({"conanfile.py": conanfile})
    client.run("profile new myprofile")
    client.run("profile update settings.os=Linux myprofile")
    client.run("install . -pr=myprofile --build")
    assert "PKGOS=Linux" in client.out
    mkdir(os.path.join(client.current_folder, "myprofile"))
    client.run("install . -pr=myprofile")
    client.run("profile new myotherprofile")
    client.run("profile update settings.os=FreeBSD myotherprofile")
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
    assert "ERROR: Exiting with code: 2" in client.out

    # Path with wrong conanfile.txt path
    client.run("install not_real_dir/conanfile.txt --install-folder subdir", assert_error=True)
    assert "Conanfile not found" in client.out

    # Path with wrong conanfile.py path
    client.run("install not_real_dir/conanfile.py --install-folder build", assert_error=True)
    assert "Conanfile not found" in client.out


def test_install_broken_reference(client):
    client.save({"conanfile.py": GenConanfile()})
    client.run("export . Hello/0.1@lasote/stable")
    client.run("remote add_ref Hello/0.1@lasote/stable default")
    ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
    # Because the folder is removed, the metadata is removed and the
    # origin remote is lost
    rmdir(os.path.join(client.cache.package_layout(ref).base_folder()))
    client.run("install Hello/0.1@lasote/stable", assert_error=True)
    assert "ERROR: Unable to find 'Hello/0.1@lasote/stable' in remotes" in client.out

    # If it was associated, it has to be desasociated
    client.run("remote remove_ref Hello/0.1@lasote/stable")
    client.run("install Hello/0.1@lasote/stable", assert_error=True)
    assert "ERROR: Unable to find 'Hello/0.1@lasote/stable' in remotes" in client.out


def test_install_argument_order(client):
    # https://github.com/conan-io/conan/issues/2520
    conanfile_boost = textwrap.dedent("""
        from conans import ConanFile
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
    client.run("install . -o boost:shared=True --build=missing")
    output_0 = "%s" % client.out
    client.run("install . -o boost:shared=True --build missing")
    output_1 = "%s" % client.out
    client.run("install -o boost:shared=True . --build missing")
    output_2 = "%s" % client.out
    client.run("install -o boost:shared=True --build missing .")
    output_3 = "%s" % client.out
    assert "ERROR" not in output_3
    assert output_0 == output_1
    assert output_1 == output_2
    assert output_2 == output_3

    client.run("install -o boost:shared=True --build boost . --build missing")
    output_4 = "%s" % client.out
    client.run("install -o boost:shared=True --build missing --build boost .")
    output_5 = "%s" % client.out
    assert output_4 == output_5


def test_install_anonymous(client):
    # https://github.com/conan-io/conan/issues/4871
    client.save({"conanfile.py": GenConanfile("Pkg", "0.1")})
    client.run("create . lasote/testing")
    client.run("upload * --confirm --all")

    client2 = TestClient(servers=client.servers, users={})
    client2.run("install Pkg/0.1@lasote/testing")
    assert "Pkg/0.1@lasote/testing: Package installed" in client2.out


def test_install_without_ref(client):
    client.save({"conanfile.py": GenConanfile("lib", "1.0")})
    client.run('create .')
    assert "lib/1.0: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID) in client.out

    client.run('upload lib/1.0 -c --all')
    assert "Uploaded conan recipe 'lib/1.0' to 'default'" in client.out

    client.run('remove "*" -f')

    # This fails, Conan thinks this is a path
    client.run('install lib/1.0', assert_error=True)
    fake_path = os.path.join(client.current_folder, "lib", "1.0")
    assert "Conanfile not found at {}".format(fake_path) in client.out

    # Try this syntax to upload too
    client.run('install lib/1.0@')
    client.run('upload lib/1.0@ -c --all')


def test_install_disabled_remote(client):
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload * --confirm --all -r default")
    client.run("remote disable default")
    client.run("install Pkg/0.1@lasote/testing -r default")
    assert "Pkg/0.1@lasote/testing: Already installed!" in client.out
    client.run("remote enable default")
    client.run("install Pkg/0.1@lasote/testing -r default")
    client.run("remote disable default")
    client.run("install Pkg/0.1@lasote/testing --update", assert_error=True)
    assert "ERROR: Remote 'default' is disabled" in client.out


def test_install_skip_disabled_remote():
    client = TestClient(servers=OrderedDict({"default": TestServer(),
                                             "server2": TestServer(),
                                             "server3": TestServer()}),
                        users={"default": [("lasote", "mypass")],
                               "server3": [("lasote", "mypass")]})
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload * --confirm --all -r default")
    client.run("upload * --confirm --all -r server3")
    client.run("remove * -f")
    client.run("remote disable default")
    client.run("install Pkg/0.1@lasote/testing", assert_error=False)
    assert "Trying with 'default'..." not in client.out


def test_install_without_update_fail(client):
    # https://github.com/conan-io/conan/issues/9183
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . zlib/1.0@")
    client.run("upload * --confirm --all -r default")
    client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0")})
    client.run("remote disable default")
    client.run("install .")
    assert "zlib/1.0: Already installed" in client.out


def test_install_version_range_reference(client):
    # https://github.com/conan-io/conan/issues/5905
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . pkg/0.1@user/channel")
    client.run("install pkg/[*]@user/channel")
    assert "pkg/0.1@user/channel from local cache - Cache" in client.out
    client.run("install pkg/[0.*]@user/channel")
    assert "pkg/0.1@user/channel from local cache - Cache" in client.out


def test_install_error_never(client):
    client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
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
        client.run("create . zlib/1.0@")
        client.run("create . zlib/2.0@")
        client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0")})
        client.run("install . --require-override=zlib/2.0")
        assert "zlib/2.0: Already installed" in client.out

    def test_install_cli_override_in_conanfile_txt(self, client):
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")
        client.run("create . zlib/2.0@")
        client.save({"conanfile.txt": textwrap.dedent("""\
        [requires]
        zlib/1.0
        """)}, clean_first=True)
        client.run("install . --require-override=zlib/2.0")
        assert "zlib/2.0: Already installed" in client.out

    def test_install_ref_cli_override(self, client):
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")
        client.run("create . zlib/1.1@")
        client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0")})
        client.run("create . pkg/1.0@")
        client.run("install pkg/1.0@ --require-override=zlib/1.1")
        assert "zlib/1.1: Already installed" in client.out

    def test_create_cli_override(self, client):
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")
        client.run("create . zlib/2.0@")
        client.save({"conanfile.py": GenConanfile().with_requires("zlib/1.0"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . pkg/0.1@ --require-override=zlib/2.0")
        assert "zlib/2.0: Already installed" in client.out

    def test_conditional(self, client):
        # https://github.com/conan-io/conan/issues/10045
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . cuda/10.2@")
        client.run("create . cuda/10.3@")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                options = {"with_cuda":[True,False]}
                default_options = {"with_cuda":True}
                def requirements(self):
                    if self.options.with_cuda:
                        self.requires('cuda/[>=10.1 <=11.4.2]')
            """)
        client.save({"conanfile.py": conanfile})
        client.run("install .")  # Check that without override, it resolves to 10.3
        assert "cuda/10.3" in client.out
        assert "cuda/10.2" not in client.out
        # Now check overrides for different commands
        client.run("create . opencv/1.0@ --require-override=cuda/10.2")
        assert "cuda/10.2" in client.out
        assert "cuda/10.3" not in client.out
        client.run("install . --require-override=cuda/10.2")
        assert "cuda/10.2" in client.out
        assert "cuda/10.3" not in client.out
        client.run("install opencv/1.0@ --require-override=cuda/10.2")
        assert "cuda/10.2" in client.out
        assert "cuda/10.3" not in client.out


def test_install_bintray_warning():
    server = TestServer(complete_urls=True)
    from conans.client.graph import proxy
    proxy.DEPRECATED_CONAN_CENTER_BINTRAY_URL = server.fake_url  # Mocking!
    client = TestClient(servers={"conan-center": server},
                        users={"conan-center": [("lasote", "mypass")]})
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . zlib/1.0@lasote/testing")
    client.run("upload zlib/1.0@lasote/testing --all -r conan-center")
    client.run("remove * -f")
    client.run("install zlib/1.0@lasote/testing -r conan-center")
    assert "WARN: Remote https://conan.bintray.com is deprecated and will be shut down " \
           "soon" in client.out
    client.run("install zlib/1.0@lasote/testing -r conan-center -s build_type=Debug")
    assert "WARN: Remote https://conan.bintray.com is deprecated and will be shut down " \
           "soon" not in client.out


def test_package_folder_available_consumer():
    """
    The package folder is not available when doing a consumer conan install "."
    We don't want to provide the package folder for the "cmake install" nor the "make install",
    as a consumer you could call the build system and pass the prefix PATH manually.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
    from conans import ConanFile
    from conan.tools.cmake import cmake_layout
    class HelloConan(ConanFile):

        settings = "os", "arch", "build_type"

        def layout(self):
            cmake_layout(self)

        def generate(self):
            self.output.warn("Package folder is None? {}".format(self.package_folder is None))
    """)
    client.save({"conanfile.py": conanfile})

    # Installing it with "install ." with output folder
    client.run("install . -of=my_build")
    assert "WARN: Package folder is None? True" in client.out

    # Installing it with "install ." without output folder
    client.run("install .")
    assert "WARN: Package folder is None? True" in client.out
