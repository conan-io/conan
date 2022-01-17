import hashlib
import os
import textwrap


from conans.util.files import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient
from conans.util.sha import sha1


def _check_conaninfo(client, ref, package_id, fields=None):
    assert f"{ref}:{package_id} - Build" in client.out
    ref = ConanFileReference.loads(ref)
    ref = client.cache.get_latest_rrev(ref)
    pref = PackageReference(ref, package_id)
    pref = client.cache.get_latest_prev(pref)
    folder = client.cache.pkg_layout(pref).package()
    conaninfo_path = os.path.join(folder, "conaninfo.txt")
    conaninfo = load(conaninfo_path)
    for f in fields or []:
        assert f"[{f}]" in conaninfo
    assert sha1(conaninfo.encode()) == package_id
    checksum = hashlib.sha1()
    with open(conaninfo_path, 'rb') as afile:
        buf = afile.read()
        checksum.update(buf)
    assert checksum.hexdigest() == package_id


def test_nothing():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . pkg/1.0@")
    _check_conaninfo(client, "pkg/1.0", NO_SETTINGS_PACKAGE_ID)


def test_settings():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_settings("os")})
    client.run("create . pkg/1.0@ -s os=Windows")
    _check_conaninfo(client, "pkg/1.0", "ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715", ["settings"])
    client.run("create . pkg/1.0@ -s os=Linux")
    _check_conaninfo(client, "pkg/1.0", "9a4eb3c8701508aa9458b1a73d0633783ecc2270", ["settings"])


def test_options():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_shared_option(False)})
    client.run("create . pkg/1.0@ -o pkg:shared=False")
    _check_conaninfo(client, "pkg/1.0", "55c609fe8808aa5308134cb5989d23d3caffccf2", ["options"])
    client.run("create . pkg/1.0@ -o pkg:shared=True")
    _check_conaninfo(client, "pkg/1.0", "1744785cb24e3bdca70e27041dc5abd20476f947", ["options"])


def test_double_package_id_call():
    # https://github.com/conan-io/conan/issues/3085
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            def package_id(self):
                self.output.info("Calling package_id()")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@user/testing")
    out = str(client.out)
    assert 1 == out.count("pkg/0.1@user/testing: Calling package_id()")


def test_remove_option_setting():
    # https://github.com/conan-io/conan/issues/2826
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class TestConan(ConanFile):
            settings = "os"
            options = {"opt": [True, False]}
            default_options = {"opt": False}

            def package_id(self):
                self.output.info("OPTION OPT=%s" % self.options.opt)
                del self.info.settings.os
                del self.info.options.opt
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
<<<<<<< HEAD
    client.run("create . pkg/1.0@ -s os=Windows")
    assert "pkg/1.0: OPTION OPT=False" in client.out
    assert "pkg/1.0: Package '%s' created" % NO_SETTINGS_PACKAGE_ID in client.out
    _check_conaninfo(client, "pkg/1.0", NO_SETTINGS_PACKAGE_ID)

    client.run("create . pkg/1.0@ -s os=Linux -o pkg:opt=True")
    assert "pkg/1.0: OPTION OPT=True" in client.out
    assert "pkg/1.0: Package '%s' created" % NO_SETTINGS_PACKAGE_ID in client.out
    _check_conaninfo(client, "pkg/1.0", NO_SETTINGS_PACKAGE_ID)
=======
    client.run("create . pkg/0.1@user/testing -s os=Windows")
    assert "pkg/0.1@user/testing: OPTION OPT=False" in client.out
    assert "pkg/0.1@user/testing: Package '%s' created" % NO_SETTINGS_PACKAGE_ID in client.out
    client.run("create . pkg/0.1@user/testing -s os=Linux -o pkg:opt=True")
    assert "pkg/0.1@user/testing: OPTION OPT=True" in client.out
    assert "pkg/0.1@user/testing: Package '%s' created" % NO_SETTINGS_PACKAGE_ID in client.out
>>>>>>> develop2


def test_value_parse():
    # https://github.com/conan-io/conan/issues/2816
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os"
            def package_id(self):
                self.info.settings.os = "kk=kk"
        """)
<<<<<<< HEAD

    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/1.0@")
    client.run("list package-ids pkg/1.0@")
    # TODO: Ugly output
    assert "os=kk=kk" in client.out

    client.run("upload pkg/1.0@ --all")
    client.run("list package-ids pkg/1.0@ -r=default")
    assert "os=kk=kk" in client.out

    client.run("remove * --force")
    client.run("install pkg/1.0@")
    client.run("list package-ids pkg/1.0@")
    assert "os=kk=kk" in client.out
=======
    server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
    servers = {"default": server}
    client = TestClient(servers=servers, inputs=["lasote", "mypass"])
    client.save({"conanfile.py": conanfile,
                 "header.h": "header content"})
    client.run("create . danimtb/testing")
    client.run("search test/0.1@danimtb/testing")
    assert "arch: kk=kk" in client.out
    client.run("upload test/0.1@danimtb/testing --all -r default")
    client.run("remove test/0.1@danimtb/testing --force")
    client.run("install --reference=test/0.1@danimtb/testing")
    client.run("search test/0.1@danimtb/testing")
    assert "arch: kk=kk" in client.out
>>>>>>> develop2


def test_option_in():
    # https://github.com/conan-io/conan/issues/7299
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class TestConan(ConanFile):
            options = {"fpic": [True, False]}
            default_options = {"fpic": True}
            def package_id(self):
                if "fpic" in self.options:
                    self.output.info("fpic is an option!!!")
                if "fpic" in self.info.options:  # Not documented
                    self.output.info("fpic is an info.option!!!")
                if "other" not in self.options:
                    self.output.info("other is not an option!!!")
                if "other" not in self.info.options:  # Not documented
                    self.output.info("other is not an info.option!!!")
                try:
                    self.options.whatever
                except Exception as e:
                    self.output.error("OPTIONS: %s" % e)
                try:
                    self.info.options.whatever
                except Exception as e:
                    self.output.error("INFO: %s" % e)

        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@user/testing")
    assert "fpic is an option!!!" in client.out
    assert "fpic is an info.option!!!" in client.out
    assert "other is not an option!!!" in client.out
    assert "other is not an info.option!!!" in client.out
    assert "ERROR: OPTIONS: option 'whatever' doesn't exist" in client.out
    assert "ERROR: INFO: option 'whatever' doesn't exist" in client.out


def test_build_type_remove_windows():
    # https://github.com/conan-io/conan/issues/7603
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            def package_id(self):
                if self.settings.os == "Windows" and self.settings.compiler == "Visual Studio":
                   del self.info.settings.build_type
                   del self.info.settings.compiler.runtime
        """)
    client.save({"conanfile.py": conanfile})
    client.run('create . pkg/1.0@ -s os=Windows -s compiler="Visual Studio" '
               '-s compiler.version=14 -s build_type=Release')
<<<<<<< HEAD

    package_id = "acb7163a9dfed39602e2f1c7acefe25a697de355"
    _check_conaninfo(client, "pkg/1.0", package_id)
    client.run('install pkg/1.0@ -s os=Windows -s compiler="Visual Studio" '
               '-s compiler.version=14 -s build_type=Debug')
    assert f"pkg/1.0:{package_id} - Cache" in client.out
=======
    assert "pkg/0.1:1454da99f096a6347c915bbbd244d7137a96d1be - Build" in client.out
    client.run('install --reference=pkg/0.1@ -s os=Windows -s compiler="Visual Studio" '
               '-s compiler.version=14 -s build_type=Debug')
    client.assert_listed_binary({"pkg/0.1": ("1454da99f096a6347c915bbbd244d7137a96d1be", "Cache")})

>>>>>>> develop2
