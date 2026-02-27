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
