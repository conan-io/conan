import textwrap

from conans.test.utils.tools import TestClient


def test_configure_args():
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            def build(self):
                cmake = CMake(self)
                cmake.configure(variables={"MYVAR": "MYVALUE"})
                cmake.build(cli_args=["--verbosebuild"], build_tool_args=["-something"])
                cmake.test(cli_args=["--testverbose"], build_tool_args=["-testok"])

            def run(self, *args, **kwargs):
                self.output.info("MYRUN: {}".format(*args))
            """)
    client.save({"conanfile.py": conanfile})
    client.run("create . ")
    # TODO: This check is ugly, because the command line is so different in each platform,
    #  and args_to_string() is doing crazy stuff
    assert '-DMYVAR="MYVALUE"' in client.out
    assert "--verbosebuild" in client.out
    assert "-something" in client.out
    assert "--testverbose" in client.out
    assert "-testok" in client.out
