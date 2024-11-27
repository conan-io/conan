import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_build_requires_options_different():
    # copied from https://github.com/conan-io/conan/pull/9839
    # This is a test that crashed in 1.X, because of conflicting options
    client = TestClient()

    conanfile_openssl_1_1_1 = GenConanfile("openssl", "1.1.1")
    conanfile_openssl_3_0_0 = GenConanfile("openssl", "3.0.0") \
        .with_option("no_fips", [True, False]) \
        .with_default_option("no_fips", True)
    conanfile_cmake = GenConanfile("cmake", "0.1") \
        .with_requires("openssl/1.1.1")
    conanfile_consumer = GenConanfile("consumer", "0.1") \
        .with_build_requires("cmake/0.1") \
        .with_requires("openssl/3.0.0")

    client.save({"openssl_1_1_1.py": conanfile_openssl_1_1_1,
                 "openssl_3_0_0.py": conanfile_openssl_3_0_0,
                 "conanfile_cmake.py": conanfile_cmake,
                 "conanfile.py": conanfile_consumer})

    client.run("create openssl_1_1_1.py")
    client.run("create openssl_3_0_0.py")
    client.run("create conanfile_cmake.py")
    client.run("install conanfile.py")
    # This test used to crash, not crashing means ok
    assert "openssl/1.1.1" in client.out
    assert "openssl/3.0.0: Already installed!" in client.out
    assert "cmake/0.1: Already installed!" in client.out


def test_different_options_values_profile():
    """
    consumer -> protobuf (library)
        \\--(build)-> protobuf (protoc)
    protobuf by default is a static library (shared=False)
    The profile or CLI args can select for each one (library and protoc) the "shared" value
    """
    c = TestClient()
    protobuf = textwrap.dedent("""
        from conan import ConanFile
        class Proto(ConanFile):
            options = {"shared": [True, False]}
            default_options = {"shared": False}

            def package_info(self):
                self.output.info("MYOPTION: {}-{}".format(self.context, self.options.shared))
        """)

    c.save({"protobuf/conanfile.py": protobuf,
            "consumer/conanfile.py": GenConanfile().with_requires("protobuf/1.0")
           .with_build_requires("protobuf/1.0")})

    c.run("create protobuf --name=protobuf --version=1.0")
    c.run("create protobuf --name=protobuf --version=1.0 -o protobuf/*:shared=True")
    c.run("install consumer")
    assert "protobuf/1.0: MYOPTION: host-False" in c.out
    assert "protobuf/1.0: MYOPTION: build-False" in c.out
    # specifying it in the profile works
    c.run("install consumer -o protobuf/*:shared=True")
    assert "protobuf/1.0: MYOPTION: host-True" in c.out
    assert "protobuf/1.0: MYOPTION: build-False" in c.out
    c.run("install consumer -o protobuf/*:shared=True -o:b protobuf/*:shared=False")
    assert "protobuf/1.0: MYOPTION: host-True" in c.out
    assert "protobuf/1.0: MYOPTION: build-False" in c.out
    c.run("install consumer -o protobuf/*:shared=False -o:b protobuf/*:shared=True")
    assert "protobuf/1.0: MYOPTION: host-False" in c.out
    assert "protobuf/1.0: MYOPTION: build-True" in c.out
    c.run("install consumer -o:b protobuf/*:shared=True")
    assert "protobuf/1.0: MYOPTION: host-False" in c.out
    assert "protobuf/1.0: MYOPTION: build-True" in c.out


@pytest.mark.parametrize("scope", ["protobuf/*:", ""])
def test_different_options_values_recipe(scope):
    """
    consumer -> protobuf (library)
        \\--(build)-> protobuf (protoc)
    protobuf by default is a static library (shared=False)
    The "consumer" conanfile.py can use ``self.requires(...,options=)`` to define protobuf:shared
    """
    c = TestClient()
    protobuf = textwrap.dedent("""
        from conan import ConanFile
        class Proto(ConanFile):
            options = {"shared": [True, False]}
            default_options = {"shared": False}

            def package_info(self):
                self.output.info("MYOPTION: {}-{}".format(self.context, self.options.shared))
        """)
    consumer_recipe = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            def requirements(self):
                self.requires("protobuf/1.0", options={{"{scope}shared": {host}}})
            def build_requirements(self):
                self.build_requires("protobuf/1.0", options={{"{scope}shared": {build}}})
        """)
    c.save({"conanfile.py": protobuf})

    c.run("create . --name=protobuf --version=1.0")
    c.run("create . --name=protobuf --version=1.0 -o protobuf/*:shared=True")

    for host, build in ((True, True), (True, False), (False, True), (False, False)):
        c.save({"conanfile.py": consumer_recipe.format(host=host, build=build, scope=scope)})
        c.run("install .")
        assert f"protobuf/1.0: MYOPTION: host-{host}" in c.out
        assert f"protobuf/1.0: MYOPTION: build-{build}" in c.out


def test_different_options_values_recipe_attributes():
    """
    consumer -> protobuf (library)
        \\--(build)-> protobuf (protoc)
    protobuf by default is a static library (shared=False)
    The "consumer" conanfile.py can use ``default_options`` to define protobuf:shared
    """
    c = TestClient()
    protobuf = textwrap.dedent("""
        from conan import ConanFile
        class Proto(ConanFile):
            options = {"shared": [True, False]}
            default_options = {"shared": False}

            def package_info(self):
                self.output.info("MYOPTION: {}-{}".format(self.context, self.options.shared))
        """)
    c.save({"conanfile.py": protobuf})
    c.run("create . --name=protobuf --version=1.0")
    c.run("create . --name=protobuf --version=1.0 -o protobuf/*:shared=True")

    consumer_recipe = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            default_options = {{"protobuf/*:shared": {host}}}
            default_build_options = {{"protobuf/*:shared": {build}}}
            def requirements(self):
                self.requires("protobuf/1.0")
            def build_requirements(self):
                self.build_requires("protobuf/1.0")
        """)

    for host, build in ((True, True), (True, False), (False, True), (False, False)):
        c.save({"conanfile.py": consumer_recipe.format(host=host, build=build)})
        c.run("install .")
        assert f"protobuf/1.0: MYOPTION: host-{host}" in c.out
        assert f"protobuf/1.0: MYOPTION: build-{build}" in c.out


def test_different_options_values_recipe_priority():
    """
    consumer ---> mypkg ---> protobuf (library)
                  \\--(build)-> protobuf (protoc)
    protobuf by default is a static library (shared=1)
    "consumer" defines a protobuf:shared=3 value, that must be respected for HOST context
    But build context, it is assigned by "mypkg", and build-require is private
    """
    c = TestClient()
    protobuf = textwrap.dedent("""
        from conan import ConanFile
        class Proto(ConanFile):
            options = {"shared": [1, 2, 3]}
            default_options = {"shared": 1}

            def package_id(self):
                self.output.info("MYOPTION: {}-{}".format(self.context, self.info.options.shared))
        """)
    my_pkg = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            def requirements(self):
                self.requires("protobuf/1.0", options={"shared": 2})
            def build_requirements(self):
                self.build_requires("protobuf/1.0", options={"shared": 2})
        """)
    c.save({"protobuf/conanfile.py": protobuf,
            "mypkg/conanfile.py": my_pkg,
            "consumer/conanfile.py": GenConanfile().with_requires("mypkg/1.0")
           .with_default_option("protobuf/*:shared", 3)})

    c.run("create protobuf --name=protobuf --version=1.0 -o protobuf/*:shared=2")
    c.run("create protobuf --name=protobuf --version=1.0 -o protobuf/*:shared=3")
    c.run("create mypkg --name=mypkg --version=1.0")

    c.run("install consumer")
    assert f"protobuf/1.0: MYOPTION: host-3" in c.out
    assert f"protobuf/1.0: MYOPTION: build-2" in c.out
