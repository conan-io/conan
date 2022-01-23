from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_env_vars_from_build_require():
    br = str(GenConanfile().with_name("hello_compiler").with_version("1.0").with_import("import os"))
    br += """
    def package_info(self):
        {}
    """
    vs = ["CC", "CC_LD", "CXX", "CXX_LD", "AR", "STRIP", "AS", "WINDRES", "PKG_CONFIG", "LD"]
    lines = "\n        ".join(['self.buildenv_info.define("{var}", "{var}_VALUE")'.format(var=var)
                               for var in vs])
    cf = br.format(lines)

    client = TestClient()
    client.save({"conanfile.py": cf})
    client.run("create .")

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_name("consumer").with_version("1.0").with_generator("MesonToolchain")\
        .with_build_requirement("hello_compiler/1.0")
    client.save({"conanfile.py": conanfile})
    client.run("install . -pr:h=default -pr:b=default")
    content = client.load("conan_meson_native.ini")
    assert "c = 'CC_VALUE'" in content
    assert "cpp = 'CXX_VALUE'" in content
    assert "c_ld = 'CC_LD_VALUE'" in content
    assert "cpp_ld = 'CXX_LD_VALUE'" in content
    assert "ar = 'AR_VALUE'" in content
    assert "strip = 'STRIP_VALUE'" in content
    assert "as = 'AS_VALUE'" in content
    assert "windres = 'WINDRES_VALUE'" in content
    assert "pkgconfig = 'PKG_CONFIG_VALUE'" in content

    # Now change the build require to declare only LD
    lines = '\n        self.buildenv_info.define("LD", "LD_VALUE")'
    cf = br.format(lines)
    client = TestClient()
    client.save({"conanfile.py": cf})
    client.run("create .")

    # Create the consumer again, now the LD env var will be applied
    client.save({"conanfile.py": conanfile})
    client.run("install . -pr:h=default -pr:b=default")
    content = client.load("conan_meson_native.ini")
    assert "c_ld = 'LD_VALUE'" in content
    assert "cpp_ld = 'LD_VALUE'" in content
