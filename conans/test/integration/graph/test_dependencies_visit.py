import textwrap

import pytest

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
                self.output.info("DefRef: {}!!!".format(dep.ref.repr_notime()))
                self.output.info("DefPRef: {}!!!".format(dep.pref.repr_notime()))
                dep = self.dependencies.build["openssl"]
                self.output.info("DefRefBuild: {}!!!".format(dep.ref.repr_notime()))
                self.output.info("DefPRefBuild: {}!!!".format(dep.pref.repr_notime()))
                for r, d in self.dependencies.build.items():
                    self.output.info("DIRECTBUILD {}: {}".format(r.direct, d))
        """)
    client.save({"conanfile.py": conanfile})

    client.run("install .")
    assert "DefRef: openssl/0.1#b3b97aecc1d4fae5f8f1c5b715079009!!!" in client.out
    assert "DefPRef: openssl/0.1#b3b97aecc1d4fae5f8f1c5b715079009:"\
           "012cdbad7278c98ff196ee2aa8f1158dde7d3c61#"\
           "2c6e0edc67e611f1acc542dd3c74dd59!!!" in client.out

    assert "DefRefBuild: openssl/0.2#b3b97aecc1d4fae5f8f1c5b715079009!!!" in client.out
    assert "DefPRefBuild: openssl/0.2#b3b97aecc1d4fae5f8f1c5b715079009:" \
           "012cdbad7278c98ff196ee2aa8f1158dde7d3c61#"\
           "2c6e0edc67e611f1acc542dd3c74dd59!!!" in client.out

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


asserts = [
    ('print("=>{}".format(self.dependencies["zlib"].ref))',
     False, "=>zlib/0.2"),
    ('print("=>{}".format(self.dependencies.get("zlib", build=True).ref))',
     False, "=>zlib/0.1"),
    ('print("=>{}".format(self.dependencies.get("zlib", build=None).ref))',
     False, "=>zlib/0.2"),
    ('print("=>{}".format(self.dependencies.get("zlib", build=True, visible=True).ref))',
     False, "=>zlib/0.1"),
    ('self.dependencies.get("cmake", build=True)', True,
     'There are more than one requires matching the specified filters: {\'build\': True}\n'
     '- cmake/0.1, Traits: build=True, headers=False, libs=False, run=False, visible=False\n'
     '- cmake/0.2, Traits: build=True, headers=False, libs=False, run=False, visible=False'
     ),
    ('self.dependencies["missing"]', True, "'missing' not found in the dependency set"),
]


@pytest.mark.parametrize("generates_line, assert_error, output_text", asserts)
def test_cmake_zlib(generates_line, assert_error, output_text):
    # app (br)---> cmake (0.1) -> zlib/0.1
    #  \     ----> zlib/0.2
    #  \  (br)---> cmake (0.2)
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . zlib/0.1@")
    client.run("create . zlib/0.2@")

    client.save({"conanfile.py": GenConanfile().with_build_requirement("zlib/0.1", visible=True)})
    client.run("create . cmake/0.1@")

    client.save({"conanfile.py": GenConanfile()})
    client.run("create . cmake/0.2@")

    app_conanfile = textwrap.dedent("""
    from conans import ConanFile
    class Pkg(ConanFile):
        def build_requirements(self):
            self.requires("cmake/0.1", headers=False, libs=False, visible=False, build=True, run=False)
            self.requires("cmake/0.2", headers=False, libs=False, visible=False, build=True, run=False)

        def requirements(self):
            self.requires("zlib/0.2")

        def generate(self):
           {}
        """.format(generates_line))
    client.save({"conanfile.py": app_conanfile})
    client.run("create . app/1.0@", assert_error=assert_error)
    assert output_text in client.out
