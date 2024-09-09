import textwrap

from conan.test.utils.tools import TestClient, GenConanfile


def test_transitive_editables_half_diamond():
    # https://github.com/conan-io/conan/issues/4445
    client = TestClient()
    client.save({"libc/conanfile.py": GenConanfile("libc", "0.1"),
                 "libb/conanfile.py": GenConanfile("libb", "0.1").with_require("libc/0.1"),
                 "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("libb/0.1",
                                                                                "libc/0.1")})
    client.run("editable add libc")
    client.run("create libb")
    client.run("install liba")
    assert "libc/0.1 - Editable" in client.out
    with client.chdir("liba/build"):
        client.run("install ..")
        assert "libc/0.1 - Editable" in client.out


def test_transitive_editable_test_requires():
    """
    This test was crashing because editable packages was "SKIP"ing some dependencies as
    "test_requires", but editables need the dependencies to generate() and to build()

    https://github.com/conan-io/conan/issues/13543
    """
    c = TestClient()
    pkga = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps, cmake_layout

        class Pkg(ConanFile):
            name = "pkga"
            version = "1.0"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            def build_requirements(self):
                self.test_requires("gtest/1.0")

            def layout(self):
                cmake_layout(self)

            def generate(self):
                cd = CMakeDeps(self)
                cd.generate()
        """)
    pkgb = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Pkg(ConanFile):
            name = "pkgb"
            version = "1.0"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires("pkga/1.0")

            def layout(self):
                cmake_layout(self)
            """)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "1.0"),
            "pkga/conanfile.py": pkga,
            "pkgb/conanfile.py": pkgb})
    c.run("create gtest")
    c.run("build pkga")
    c.run("editable add pkga")
    # This used to crash, due to paths in test_requires not being processed (package_info() not
    # being called
    c.run("build pkgb")


def test_transitive_editables_python_requires_version_range():
    # https://github.com/conan-io/conan/issues/14411
    client = TestClient(default_server_user=True)
    client.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                 "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("dep/[*]")})
    client.run("editable add pkg", assert_error=True)
    assert "Version range '*' from requirement 'dep/[*]' required by 'python_requires' " \
           "could not be resolved" in client.out
    client.run("export dep")
    client.run("upload * -r=default -c")
    client.run("remove * -c")
    client.run("editable add pkg")  # now it works, able to return from server if necessary
    assert "dep/0.1: Downloaded recipe revision" in client.out


def test_transitive_editables_build():
    # https://github.com/conan-io/conan/issues/6064
    c = TestClient()
    libb = textwrap.dedent("""\
        from conan import ConanFile
        class LibB(ConanFile):
            name = "libb"
            version = "0.1"
            build_policy = "missing"
            settings = "os", "compiler", "arch"

            def build_requirements(self):
                self.build_requires("liba/[>=0.0]")

            def requirements(self):
                self.requires("liba/[>=0.0]")
        """)
    c.save({"liba/conanfile.py": GenConanfile("liba", "0.1"),
            "libb/conanfile.py": libb,
            "app/conanfile.txt": "[requires]\nlibb/0.1"})
    c.run("editable add liba")
    c.run("editable add libb")
    c.run("install app --build=*")
    # It doesn't crash
    # Try also with 2 profiles
    c.run("install app -s:b os=Windows --build=*")
    # it doesn't crash


def test_transitive_editable_cascade_build():
    """
    https://github.com/conan-io/conan/issues/15292
    """
    c = TestClient()
    pkga = GenConanfile("pkga", "1.0").with_package_type("static-library")
    pkgb = GenConanfile("pkgb", "1.0").with_requires("pkga/1.0").with_package_type("static-library")
    pkgc = GenConanfile("pkgc", "1.0").with_requires("pkgb/1.0").with_package_type("static-library")
    app = GenConanfile("app", "1.0").with_requires("pkgc/1.0").with_package_type("application")
    c.save({"pkga/conanfile.py": pkga,
            "pkgb/conanfile.py": pkgb,
            "pkgc/conanfile.py": pkgc,
            "app/conanfile.py": app})
    c.run("create pkga")
    c.run("create pkgb")
    pkgb_id = c.created_package_id("pkgb/1.0")
    c.run("create pkgc")
    pkgc_id = c.created_package_id("pkgc/1.0")
    c.run("install app")
    # now we want to investigate pkga
    c.run("editable add pkga")
    pkga = GenConanfile("pkga", "1.0").with_package_type("static-library")\
                                      .with_class_attribute("some=42")
    c.save({"pkga/conanfile.py": pkga})
    c.run("install app")
    # The consumers didn't need a new binary, even if I modified pkg
    c.assert_listed_binary({"pkgb/1.0": (pkgb_id, "Cache"),
                            "pkgc/1.0": (pkgc_id, "Cache")})
    c.run("install app --build=editable")
    c.assert_listed_binary({"pkgb/1.0": (pkgb_id, "Cache"),
                            "pkgc/1.0": (pkgc_id, "Cache")})
    # But I can command perfectly what to do and when
    c.run("install app --build=editable --build=cascade")
    c.assert_listed_binary({"pkgb/1.0": (pkgb_id, "Build"),
                            "pkgc/1.0": (pkgc_id, "Build")})

    # Changes in pkga are good, we export it
    c.run("export pkga")
    # Now we remove the editable
    c.run("editable remove pkga")
    c.run("install app", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkga/1.0'" in c.out


def test_transitive_editable_cascade_package_id():
    """
    https://github.com/conan-io/conan/issues/15292
    """
    c = TestClient()
    pkga = GenConanfile("pkga", "1.0").with_package_type("static-library")
    pkgb = GenConanfile("pkgb", "1.0").with_requires("pkga/1.0").with_package_type("static-library")
    pkgc = GenConanfile("pkgc", "1.0").with_requires("pkgb/1.0").with_package_type("shared-library")
    app = GenConanfile("app", "1.0").with_requires("pkgc/1.0").with_package_type("application")
    c.save({"pkga/conanfile.py": pkga,
            "pkgb/conanfile.py": pkgb,
            "pkgc/conanfile.py": pkgc,
            "app/conanfile.py": app})
    c.run("create pkga")
    c.run("create pkgb")
    pkgb_id = c.created_package_id("pkgb/1.0")
    c.run("create pkgc")
    c.run("install app")

    # now we want to investigate pkga, we put it in editable mode
    c.run("editable add pkga")
    pkga = GenConanfile("pkga", "1.0").with_package_type("static-library")\
                                      .with_class_attribute("some=42")
    c.save({"pkga/conanfile.py": pkga})
    c.run("install app", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkgc/1.0'" in c.out
    c.run("install app --build=missing")
    pkgc_id = c.created_package_id("pkgc/1.0")
    # The consumers didn't need a new binary, even if I modified pkg
    c.assert_listed_binary({"pkgb/1.0": (pkgb_id, "Cache"),
                            "pkgc/1.0": (pkgc_id, "Build")})

    # Changes in pkga are good, we export it
    c.run("export pkga")
    # Now we remove the editable
    c.run("editable remove pkga")
    c.run("install app", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkgc/1.0'" in c.out
    c.run("install app --build=missing")
    pkgc_id = c.created_package_id("pkgc/1.0")
    # The consumers didn't need a new binary, even if I modified pkg
    c.assert_listed_binary({"pkgb/1.0": (pkgb_id, "Cache"),
                            "pkgc/1.0": (pkgc_id, "Build")})
