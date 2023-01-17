import textwrap

from conans.test.utils.tools import TestClient


def test_cross_build_options():
    # https://github.com/conan-io/conan/issues/8443
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            options = {"fPIC": [True, False]}
            default_options = {"fPIC": True}
            settings = "os"
            def config_options(self):
                if self.settings.os == "Windows":
                    del self.options.fPIC
            """)
    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            requires = "dep/0.1"
            tool_requires = "dep/0.1"
        """)
    c.save({"dep/conanfile.py": dep,
            "consumer/conanfile.py": consumer})
    c.run("create dep -s os=Android -s os.api_level=22")
    c.run("create dep -s os=Windows")
    c.run("install consumer -s:b os=Windows -s:h os=Android -s:h os.api_level=22")
    assert "dep/0.1:0e4b89e69f340b0e6f4b08523b5215bacf5eae3e - Cache" in c.out
    assert "dep/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Cache" in c.out
