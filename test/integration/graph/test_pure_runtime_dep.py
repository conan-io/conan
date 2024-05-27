from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_pure_runtime_dep():
    c = TestClient()
    c.save({"tooldep/conanfile.py": GenConanfile("tooldep", "0.1").with_package_file("bin/mysh",
                                                                                     "myshared")
                                                                  .with_package_type("shared-library"),
            "tool/conanfile.py": GenConanfile("tool", "0.1").with_requirement("tooldep/0.1")
                                                            .with_package_file("bin/myexe", "exe"),
            "lib/conanfile.py": GenConanfile("lib", "0.1").with_requirement("tool/0.1",
                                                                            headers=False,
                                                                            libs=False, run=True),
            "consumer/conanfile.py": GenConanfile().with_settings("build_type", "os",
                                                                  "compiler", "arch")
                                                   .with_requires("lib/0.1")})

    c.run("create tooldep")
    c.run("create tool")
    c.run("create lib")
    c.run("install consumer -g CMakeDeps")
