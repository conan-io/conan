import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_timestamp_error():
    """ this test is a reproduction for
    # https://github.com/conan-io/conan/issues/11606

    It was crashing because of multiple test_requires, some of them being BINARY_SKIP,
    and the prev_timestamp was not being assigned by GraphBinariesAnalizer when caching
    """

    c = TestClient(default_server_user=True)
    engine = textwrap.dedent("""
        from conan import ConanFile

        class Engine(ConanFile):
            name = "engine"
            version = "0.1"
            def build_requirements(self):
                self.test_requires("gtest/0.1")
        """)
    app = textwrap.dedent("""
        from conan import ConanFile
        class App(ConanFile):
            def requirements(self):
                self.requires("engine/0.1")
            def build_requirements(self):
                self.test_requires("gtest/0.1")
        """)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "0.1"),
            "engine/conanfile.py": engine,
            "app/conanfile.py": app})
    c.run("create gtest")
    c.run("create engine")
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("install app")
    # This used to fail, now it is not crashing anymore
    assert "Finalizing install" in c.out


def test_reupload_older_revision_new_binaries_conan_server():
    """ upload maintains the server history and revision order
        https://github.com/conan-io/conan/pull/16621
        no matter the elapsed time, or the --force, order is always preserved

        This is not the case for Artifactory, that introduced a conf defaulting to 60 seconds,
        so forced uploads will make the timestamp the latest
    """
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")})
    c.run("create . -s os=Linux")
    rrev1 = c.exported_recipe_revision()
    c.run("upload * -r=default -c")

    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")
                                                      .with_class_attribute("potato = 42")})
    c.run("create . -s os=Linux")
    rrev2 = c.exported_recipe_revision()
    c.run("upload * -r=default -c")

    def check_order():
        c.run("list pkg/0.1#* -r=default")
        out = str(c.out)
        assert rrev1 in out
        assert rrev2 in out
        assert out.find(rrev1) < out.find(rrev2)

    check_order()

    # If we create the same older revision, and upload, still the same order
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")})
    c.run("create . -s os=Windows")
    rrev3 = c.exported_recipe_revision()
    assert rrev3 == rrev1
    # import time
    # time.sleep(65)
    c.run(f"upload pkg*#{rrev3} -r=default -c --force")

    check_order()
