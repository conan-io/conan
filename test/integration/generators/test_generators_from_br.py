import textwrap

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
        """)})

    tc.run("create tool")
    tc.run("install --tool-requires=tool/0.1")
    assert "WARN: experimental: Tool-require tool/0.1 adding generators: " \
           "['CMakeToolchain', 'MyGenerator']" in tc.out
    assert "Generator 'CMakeToolchain' calling 'generate()'" in tc.out
    assert "Generator 'MyGenerator' calling 'generate()'" in tc.out
    assert "CMakeToolchain generated: conan_toolchain.cmake" in tc.out
    assert "MyGenerator generated" in tc.out


def test_inject_generators_error():
    c = TestClient(light=True)
    c.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile

        class ToolConan(ConanFile):
            name = "tool"
            version = "0.1"

            def package_info(self):
                self.generator_info = "CMakeToolchain"
        """)})
    c.run("create .")
    c.run("install --tool-requires=tool/0.1", assert_error=True)
    assert "ERROR: tool/0.1 'generator_info' must be a list" in c.out


def test_inject_vars():
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
        """)})

    tc.run("create tool")
    tc.run(f"install --tool-requires=tool/0.1")

    content = tc.load("conanbuild.sh")
    assert "conantest.sh" in content
    assert "envars_generator2.sh" in content
