import textwrap

from conans.test.utils.tools import TestClient


def test_custom_block():
    # https://github.com/conan-io/conan/issues/9998
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMakeToolchain
        class Pkg(ConanFile):
            def generate(self):
                toolchain = CMakeToolchain(self)

                class MyBlock:
                    template = "Hello {{myvar}}!!!"

                    def context(self):
                        return {"myvar": "World"}

                toolchain.blocks["mynewblock"] = MyBlock
                toolchain.generate()
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install .")
    assert "Hello World!!!" in c.load("conan_toolchain.cmake")
