import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_dependencies_visit():
    client = TestClient(light=True)
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

                if "openssl" in self.dependencies:
                    self.output.info("OpenSSL found in deps")

                if "cmake" in self.dependencies:
                    self.output.info("cmake found in default deps")

                if "cmake" in self.dependencies.build:
                    self.output.info("cmake found in deps.build")

                if "badlib" in self.dependencies:
                    self.output.info("badlib found in deps")
        """)
    client.save({"conanfile.py": conanfile})

    client.run("install .")
    refs = client.cache.get_latest_recipe_reference(RecipeReference.loads("openssl/0.1"))
    pkgs = client.cache.get_package_references(refs)
    prev1 = client.cache.get_latest_package_reference(pkgs[0])
    assert f"DefRef: {repr(prev1.ref)}!!!" in client.out
    assert f"DefPRef: {prev1.repr_notime()}!!!" in client.out

    refs = client.cache.get_latest_recipe_reference(RecipeReference.loads("openssl/0.2"))
    pkgs = client.cache.get_package_references(refs)
    prev2 = client.cache.get_latest_package_reference(pkgs[0])
    assert f"DefRefBuild: {repr(prev2.ref)}!!!" in client.out
    assert f"DefPRefBuild: {prev2.repr_notime()}!!!" in client.out

    assert "conanfile.py: DIRECTBUILD True: cmake/0.1" in client.out
    assert "conanfile.py: DIRECTBUILD False: openssl/0.2" in client.out

    assert "OpenSSL found in deps" in client.out
    assert "badlib found in deps" not in client.out

    assert "cmake found in default deps" not in client.out
    assert "cmake found in deps.build" in client.out


def test_dependencies_visit_settings_options():
    client = TestClient(light=True)
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
    ('print("=>{}".format(self.dependencies.get("zlib", build=True, visible=False).ref))',
     False, "=>zlib/0.1"),
    ('self.dependencies.get("cmake", build=True)', True,
     'There are more than one requires matching the specified filters: {\'build\': True}\n'
     '- cmake/0.1, Traits: build=True, headers=False, libs=False, run=False, visible=False\n'
     '- cmake/0.2, Traits: build=True, headers=False, libs=False, run=False, visible=False'
     ),
    ('self.dependencies["missing"]', True, "'missing' not found in the dependency set"),
    ('self.output.info("Missing in deps: " + str("missing" in self.dependencies))', False, "Missing in deps: False"),
    ('self.output.info("Zlib in deps: " + str("zlib" in self.dependencies))', False, "Zlib in deps: True"),
    ('self.output.info("Zlib in deps.build: " + str("zlib" in self.dependencies.build))', False, "Zlib in deps.build: True"),
]


@pytest.mark.parametrize("generates_line, assert_error, output_text", asserts)
def test_cmake_zlib(generates_line, assert_error, output_text):
    # app (br)---> cmake (0.1) -> zlib/0.1
    #  \     ----> zlib/0.2
    #  \  (br)---> cmake (0.2)
    client = TestClient(light=True)
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
    client = TestClient(light=True)
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
    client = TestClient(light=True)
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
    client.run("install . -pr:b=default -pr:h=profile --build='*'")  # Use 2 contexts

    # Validate time, build-requires available
    assert "conanfile.py: VALIDATE DEPS: 1!!!" in client.out
    # generate time, build-requires already available
    assert "conanfile.py: GENERATE REQUIRE: cmake/0.1!!!" in client.out
    assert "conanfile.py: GENERATE CMAKE: cmake/0.1!!!" in client.out


def test_dependencies_package_type():
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("lib", "0.1").with_package_type("static-library")})
    c.run("create .")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "lib/0.1"
            def generate(self):
                is_app = self.dependencies["lib"].package_type == "static-library"
                self.output.info(f"APP: {is_app}!!")
                assert is_app
                self.dependencies["lib"].package_type == "not-exist-type"
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install .", assert_error=True)
    assert "APP: True!!" in c.out
    assert "conanfile.py: Error in generate() method, line 9" in c.out
    assert "ValueError: 'not-exist-type' is not a valid PackageType" in c.out


def test_dependency_interface():
    """
    Quick test for the ConanFileInterface exposed
    """
    c = TestClient(light=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "1.0"
            homepage = "myhome"
            url = "myurl"
            license = "MIT"
        """)
    user = textwrap.dedent("""
        from conan import ConanFile
        class User(ConanFile):
            requires = "dep/1.0"
            def generate(self):
                self.output.info("HOME: {}".format(self.dependencies["dep"].homepage))
                self.output.info("URL: {}".format(self.dependencies["dep"].url))
                self.output.info("LICENSE: {}".format(self.dependencies["dep"].license))
                self.output.info("RECIPE: {}".format(self.dependencies["dep"].recipe_folder))
                self.output.info("CONANDATA: {}".format(self.dependencies["dep"].conan_data))

            """)
    c.save({"dep/conanfile.py": conanfile,
            "dep/conandata.yml": "",
            "user/conanfile.py": user})
    c.run("create dep")
    c.run("install user")
    assert "conanfile.py: HOME: myhome" in c.out
    assert "conanfile.py: URL: myurl" in c.out
    assert "conanfile.py: LICENSE: MIT" in c.out
    assert "conanfile.py: RECIPE:" in c.out
    assert "conanfile.py: CONANDATA: {}" in c.out


def test_dependency_interface_validate():
    """
    In the validate() method, there is no access to dep.package_folder, because the packages are
    not there. validate() operates at the graph level, without binaries, before they are installed,
    and we want to keep it that way
    https://github.com/conan-io/conan/issues/11959
    """
    c = TestClient(light=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "1.0"
            homepage = "myhome"
        """)
    user = textwrap.dedent("""
        import os
        from conan import ConanFile
        class User(ConanFile):
            requires = "dep/1.0"
            def validate(self):
                dep = self.dependencies["dep"]
                self.output.info("HOME: {}".format(dep.homepage))
                self.output.info("PKG FOLDER: {}".format(dep.package_folder is None))
            """)
    c.save({"dep/conanfile.py": conanfile,
            "user/conanfile.py": user})
    c.run("create dep")
    c.run("install user")
    assert "conanfile.py: HOME: myhome" in c.out
    assert "conanfile.py: PKG FOLDER: True" in c.out


def test_validate_visibility():
    # https://github.com/conan-io/conan/issues/12027
    c = TestClient(light=True)
    t1 = textwrap.dedent("""
        from conan import ConanFile
        class t1Conan(ConanFile):
            name = "t1"
            version = "0.1"
            package_type = "static-library"

            def package_info(self):
                self.cpp_info.libs = ["mylib"]
        """)
    t2 = textwrap.dedent("""
        from conan import ConanFile
        class t2Conan(ConanFile):
            name = "t2"
            version = "0.1"
            requires = "t1/0.1"
            package_type = "shared-library"

            def validate(self):
                self.output.info("VALID: {}".format(self.dependencies["t1"]))
        """)
    t3 = textwrap.dedent("""
        from conan import ConanFile
        class t3Conan(ConanFile):
            name = "t3"
            version = "0.1"
            requires = "t2/0.1"
            package_type = "application"

            def validate(self):
                self.output.info("VALID: {}".format(self.dependencies["t1"]))
                self.output.info("VALID: {}".format(self.dependencies["t2"]))

            def generate(self):
                self.output.info("GENERATE: {}".format(self.dependencies["t1"]))
                self.output.info("GENERATE: {}".format(self.dependencies["t2"]))
        """)

    c.save({"t1/conanfile.py": t1,
            "t2/conanfile.py": t2,
            "t3/conanfile.py": t3})
    c.run("create t1")
    c.run("create t2")
    c.run("install t3")
    assert "t2/0.1: VALID: t1/0.1" in c.out
    assert "conanfile.py (t3/0.1): VALID: t1/0.1" in c.out
    assert "conanfile.py (t3/0.1): VALID: t2/0.1" in c.out
    assert "conanfile.py (t3/0.1): GENERATE: t1/0.1" in c.out
    assert "conanfile.py (t3/0.1): GENERATE: t2/0.1" in c.out
    c.run("create t3")
    assert "t2/0.1: VALID: t1/0.1" in c.out
    assert "t3/0.1: VALID: t1/0.1" in c.out
    assert "t3/0.1: VALID: t2/0.1" in c.out
    assert "t3/0.1: GENERATE: t1/0.1" in c.out
    assert "t3/0.1: GENERATE: t2/0.1" in c.out
