import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


def test_dependencies_visit():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_shared_option(True)})
    client.run("create . openssl/0.1@")
    client.run("create . openssl/0.2@")
    client.save({"conanfile.py": GenConanfile().with_requires("openssl/0.2")})
    client.run("create . cmake/0.1@")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/0.1"
            build_requires = "cmake/0.1"

            def generate(self):
                dep = self.dependencies["openssl"]
                self.output.info("DefRef: {}!!!".format(repr(dep.ref)))
                self.output.info("DefPRef: {}!!!".format(repr(dep.pref)))
                dep = self.dependencies.build["openssl"]
                self.output.info("DefRefBuild: {}!!!".format(repr(dep.ref)))
                self.output.info("DefPRefBuild: {}!!!".format(repr(dep.pref)))
                for r, d in self.dependencies.build.items():
                    self.output.info("DIRECTBUILD {}: {}".format(r.direct, d))
        """)
    client.save({"conanfile.py": conanfile})

    client.run("install .")
    assert "DefRef: openssl/0.1#b3b97aecc1d4fae5f8f1c5b715079009!!!" in client.out
    assert "DefPRef: openssl/0.1#b3b97aecc1d4fae5f8f1c5b715079009:"\
           "1744785cb24e3bdca70e27041dc5abd20476f947#"\
           "5c9041caa6737b80b91dae847ad118b2!!!" in client.out

    assert "DefRefBuild: openssl/0.2#b3b97aecc1d4fae5f8f1c5b715079009!!!" in client.out
    assert "DefPRefBuild: openssl/0.2#b3b97aecc1d4fae5f8f1c5b715079009:" \
           "1744785cb24e3bdca70e27041dc5abd20476f947#"\
           "5c9041caa6737b80b91dae847ad118b2!!!" in client.out

    assert "conanfile.py: DIRECTBUILD True: cmake/0.1" in client.out
    assert "conanfile.py: DIRECTBUILD False: openssl/0.2" in client.out


def test_dependencies_visit_settings_options():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_settings("os").
                with_option("shared", [True, False]).with_default_option("shared", False)})
    client.run("create . openssl/0.1@ -s os=Linux")
    client.save({"conanfile.py": GenConanfile().with_requires("openssl/0.1")})
    client.run("create . pkg/0.1@  -s os=Linux")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "pkg/0.1"

            def generate(self):
                dep = self.dependencies["openssl"]
                self.output.info("SETTINGS: {}!".format(dep.settings.os))
                self.output.info("OPTIONS: shared={}!".format(dep.options.shared))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install . -s os=Linux")
    assert "conanfile.py: SETTINGS: Linux!" in client.out
    assert "conanfile.py: OPTIONS: shared=False!" in client.out
