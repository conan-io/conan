import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient
from conans.util.files import save


def test_double_package_id_call():
    # https://github.com/conan-io/conan/issues/3085
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch"

            def package_id(self):
                self.output.info("Calling package_id()")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
    out = str(client.out)
    assert 1 == out.count("pkg/0.1@user/testing: Calling package_id()")


def test_remove_option_setting():
    # https://github.com/conan-io/conan/issues/2826
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestConan(ConanFile):
            settings = "os"
            options = {"opt": [True, False]}
            default_options = {"opt": False}

            def package_id(self):
                self.output.info("OPTION OPT=%s" % self.info.options.opt)
                del self.info.settings.os
                del self.info.options.opt
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Windows")
    assert "pkg/0.1@user/testing: OPTION OPT=False" in client.out
    assert "pkg/0.1@user/testing: Package '%s' created" % NO_SETTINGS_PACKAGE_ID in client.out
    client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux -o pkg/*:opt=True")
    assert "pkg/0.1@user/testing: OPTION OPT=True" in client.out
    assert "pkg/0.1@user/testing: Package '%s' created" % NO_SETTINGS_PACKAGE_ID in client.out


def test_value_parse():
    # https://github.com/conan-io/conan/issues/2816
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestConan(ConanFile):
            name = "test"
            version = "0.1"
            settings = "os", "arch", "build_type"

            def package_id(self):
                self.info.settings.arch = "kk=kk"
                self.info.settings.os = "yy=yy"
        """)

    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": conanfile})
    client.run("create . ")
    client.run("list *:*")
    assert "arch: kk=kk" in client.out
    client.run("upload * -r default -c")
    client.run("list *:* -r=default")
    assert "arch: kk=kk" in client.out
    client.run("remove * -c")
    client.run("install --requires=test/0.1")
    client.run("list *:*")
    assert "arch: kk=kk" in client.out


def test_option_in():
    # https://github.com/conan-io/conan/issues/7299
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class TestConan(ConanFile):
            options = {"fpic": [True, False]}
            default_options = {"fpic": True}
            def package_id(self):
                if "fpic" in self.info.options:
                    self.output.info("fpic is an option!!!")
                if "fpic" in self.info.options:  # Not documented
                    self.output.info("fpic is an info.option!!!")
                if "other" not in self.info.options:
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
    client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
    assert "fpic is an option!!!" in client.out
    assert "fpic is an info.option!!!" in client.out
    assert "other is not an option!!!" in client.out
    assert "other is not an info.option!!!" in client.out
    assert "OPTIONS: 'self.options' access in 'package_id()' method is forbidden" in client.out
    assert "ERROR: INFO: option 'whatever' doesn't exist" in client.out


def test_build_type_remove_windows():
    # https://github.com/conan-io/conan/issues/7603
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            def package_id(self):
                if self.info.settings.os == "Windows" and self.info.settings.compiler == "msvc":
                   del self.info.settings.build_type
                   del self.info.settings.compiler.runtime
                   del self.info.settings.compiler.runtime_type
        """)
    client.save({"conanfile.py": conanfile})
    client.run('create . --name=pkg --version=0.1 -s os=Windows -s compiler=msvc -s arch=x86_64 '
               '-s compiler.version=190 -s build_type=Release -s compiler.runtime=dynamic')
    package_id = "6a98270da6641cc6668b83daf547d67451910cf0"
    client.assert_listed_binary({"pkg/0.1": (package_id, "Build")})
    client.run('install --requires=pkg/0.1@ -s os=Windows -s compiler=msvc -s arch=x86_64 '
               '-s compiler.version=190 -s build_type=Debug -s compiler.runtime=dynamic')
    client.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})


def test_package_id_requires_info():
    """ if we dont restrict ``package_id()`` to use only ``self.info`` it will do nothing and fail
    if we ``del self.settings.arch`` instead of ``del self.info.settings.arch``
    https://github.com/conan-io/conan/issues/12693
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch"

            def package_id(self):
                if self.info.settings.os == "Windows":
                    del self.info.settings.arch
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1 -s os=Windows -s arch=armv8")
    client.assert_listed_binary({"pkg/0.1": ("ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715", "Build")})
    client.run("create . --name=pkg --version=0.1 -s os=Windows -s arch=x86_64")
    client.assert_listed_binary({"pkg/0.1": ("ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715", "Build")})


def test_package_id_validate_settings():
    """ ``self.info`` has no validation, as it allows to be mutated
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch"

            def package_id(self):
                if self.info.settings.os == "DONT_EXIST":
                    del self.info.settings.arch
        """)
    c = TestClient()
    c.save({"conanfile.py": conanfile})
    c.run("create . --name=pkg --version=0.1")
    # It used to fail,


class TestBuildRequiresHeaderOnly:
    def test_header_only(self):
        c = TestClient(light=True)
        save(c.cache.global_conf_path, "core.package_id:default_build_mode=minor_mode")
        pkg = textwrap.dedent("""\
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                tool_requires = "tool/[*]"
                def package_id(self):
                    self.info.clear()
                """)
        c.save({"tool/conanfile.py": GenConanfile("tool"),
                "pkg/conanfile.py": pkg})
        c.run("create tool --version=1.0")
        c.run("create pkg")
        pkgid = c.created_package_id("pkg/0.1")
        c.run("create tool --version=1.2")
        c.run("install --requires=pkg/0.1")
        c.assert_listed_binary({"pkg/0.1": (pkgid, "Cache")})

    def test_header_only_implements(self):
        c = TestClient(light=True)
        save(c.cache.global_conf_path, "core.package_id:default_build_mode=minor_mode")
        pkg = textwrap.dedent("""\
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                tool_requires = "tool/[*]"
                package_type = "header-library"
                implements = ["auto_header_only"]
                """)
        c.save({"tool/conanfile.py": GenConanfile("tool"),
                "pkg/conanfile.py": pkg})
        c.run("create tool --version=1.0")
        c.run("create pkg")
        pkgid = c.created_package_id("pkg/0.1")
        c.run("create tool --version=1.2")
        c.run("install --requires=pkg/0.1")
        c.assert_listed_binary({"pkg/0.1": (pkgid, "Cache")})


def test_explicit_implements():
    c = TestClient()
    pkg = textwrap.dedent("""\
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os"
            options = {"header_only": [True, False]}

            def package_id(self):
                if self.package_type == "header-library":
                    self.info.clear()
             """)
    c.save({"conanfile.py": pkg})
    c.run("create . -s os=Windows -o *:header_only=True")
    pkgid = c.created_package_id("pkg/0.1")
    c.run("create . -s os=Linux -o *:header_only=True")
    pkgid2 = c.created_package_id("pkg/0.1")
    assert pkgid == pkgid2

    c.run("create . -s os=Windows -o *:header_only=False")
    pkgid3 = c.created_package_id("pkg/0.1")
    assert pkgid3 != pkgid
    c.run("create . -s os=Linux -o *:header_only=False")
    pkgid4 = c.created_package_id("pkg/0.1")
    assert pkgid4 != pkgid
    assert pkgid3 != pkgid4
