import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_inject_generators_conf():
    tc = TestClient(light=True)
    tc.save({"tool/conanfile.py": textwrap.dedent("""
    from conan import ConanFile

    class MyGenerator:
        def __init__(self, conanfile):
            self.conanfile = conanfile

        def generate(self):
            self.conanfile.output.info("MyGenerator generated")

    class ToolConan(ConanFile):
        name = "tool"
        version = "0.1"

        def package_info(self):
            self.generator_info = ["CMakeToolchain", MyGenerator]
    """),
             "conanfile.py": GenConanfile("app", "1.0").with_tool_requires("tool/0.1")})

    tc.run("create tool")
    tc.run("create .")
    assert "app/1.0: CMakeToolchain generated: conan_toolchain.cmake" in tc.out
    assert "app/1.0: MyGenerator generated" in tc.out
