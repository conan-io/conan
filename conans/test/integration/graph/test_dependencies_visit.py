import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_dependencies_visit():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_shared_option(True)})
    client.run("create . --name=openssl --version=0.1")
    client.run("create . --name=openssl --version=0.2")
    client.save({"conanfile.py": GenConanfile().with_requires("openssl/0.2")})
    client.run("create . --name=cmake --version=0.1")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
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
    client.run("create . --name=openssl --version=0.1 -s os=Linux")
    client.save({"conanfile.py": GenConanfile().with_requires("openssl/0.1")})
    client.run("create . --name=pkg --version=0.1  -s os=Linux")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
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
    ('print("=>{}".format(self.dependencies.build.get("zlib").ref))',
     False, "=>zlib/0.1"),
    ('print("=>{}".format(self.dependencies.get("zlib", build=True).ref))',
     False, "=>zlib/0.1"),
    ('print("=>{}".format(self.dependencies.get("zlib", build=False).ref))',
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
    client.run("create . --name=zlib --version=0.1")
    client.run("create . --name=zlib --version=0.2")

    client.save({"conanfile.py": GenConanfile().with_tool_requirement("zlib/0.1",
                                                                            visible=True)})
    client.run("create . --name=cmake --version=0.1")

    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=cmake --version=0.2")

    app_conanfile = textwrap.dedent("""
    from conan import ConanFile
    class Pkg(ConanFile):

        def requirements(self):
            self.requires("zlib/0.2")
            self.requires("cmake/0.1", headers=False, libs=False, visible=False, build=True, run=False)
            self.requires("cmake/0.2", headers=False, libs=False, visible=False, build=True, run=False)

        def generate(self):
           {}
        """.format(generates_line))
    client.save({"conanfile.py": app_conanfile})
    client.run("create . --name=app --version=1.0", assert_error=assert_error)
    assert output_text in client.out


def test_invisible_not_colliding_test_requires():
    """
    The test_requires are private, so the app can't see them, only the foo and bar
    :return:
    """
    # app ---> foo/0.1 --test_require--> gtest/0.1
    #  \  ---> bar/0.1 --test_require--> gtest/0.2
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=gtest --version=0.1")
    client.run("create . --name=gtest --version=0.2")

    client.save({"conanfile.py": GenConanfile().with_test_requires("gtest/0.1")})
    client.run("create . --name=foo --version=0.1")

    client.save({"conanfile.py": GenConanfile().with_test_requires("gtest/0.2")})
    client.run("create . --name=bar --version=0.1")

    app_conanfile = textwrap.dedent("""
    from conan import ConanFile
    class Pkg(ConanFile):

        def requirements(self):
            self.requires("foo/0.1")
            self.requires("bar/0.1")

        def generate(self):
            print(self.dependencies.get("gtest"))
        """)
    client.save({"conanfile.py": app_conanfile})
    client.run("create . --name=app --version=1.0", assert_error=True)
    assert "'gtest' not found in the dependency set" in client.out


def test_dependencies_visit_build_requires_profile():
    """ At validate() time, in Conan 1.X, the build-requires are not available yet, because first
    the binary package_id is computed, then the build-requires are resolved.
    It is necessary to avoid in Conan 1.X the caching of the ConanFile.dependencies, because
    at generate() time it will have all the graph info, including build-requires
    """
    # https://github.com/conan-io/conan/issues/10304
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("cmake", "0.1")})
    client.run("create .")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):

            def validate(self):
                self.output.info("VALIDATE DEPS: {}!!!".format(len(self.dependencies.items())))

            def generate(self):
                for req, dep in self.dependencies.items():
                    self.output.info("GENERATE REQUIRE: {}!!!".format(dep.ref))
                dep = self.dependencies.build["cmake"]
                self.output.info("GENERATE CMAKE: {}!!!".format(dep.ref))
        """)
    client.save({"conanfile.py": conanfile,
                 "profile": "[tool_requires]\ncmake/0.1"})
    client.run("install . -pr:b=default -pr:h=profile --build")  # Use 2 contexts

    # Validate time, build-requires available
    assert "conanfile.py: VALIDATE DEPS: 1!!!" in client.out
    # generate time, build-requires already available
    assert "conanfile.py: GENERATE REQUIRE: cmake/0.1!!!" in client.out
    assert "conanfile.py: GENERATE CMAKE: cmake/0.1!!!" in client.out
