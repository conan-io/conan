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


def test_inject_vars():
    import os
    tc = TestClient(light=True)
    tc.save({
    "tool/envars_generator1.sh": textwrap.dedent("""
    export VAR1="value1"
    export PATH="$PATH:/additional/path"
    """),
    "tool/envars_generator2.sh": textwrap.dedent("""
    export VAR2="value2"
    """),
    "tool/conanfile.py": textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.env import create_env_script, register_env_script
    import os

    class GeneratorSet:
        def __init__(self, conanfile):
            self.conanfile = conanfile

        def generate(self):
            content = 'call envars_generator.sh'
            name = f"conantest.sh"
            create_env_script(self.conanfile, content, name)
            register_env_script(self.conanfile, "tool/envars_generator2.sh")

    class ToolConan(ConanFile):
        name = "tool"
        version = "0.1"

        def package_info(self):
            self.generator_info = [GeneratorSet]
    """),
             "conanfile.py": GenConanfile("app", "1.0").with_tool_requires("tool/0.1")})

    tc.run("create tool")
    tc.run(f"install . ")

    content = tc.load("conanbuild.sh")
    assert "conantest.sh" in content
    assert "envars_generator2.sh" in content
