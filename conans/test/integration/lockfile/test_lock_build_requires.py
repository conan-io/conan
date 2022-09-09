from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_lock_requires():
    c = TestClient()
    c.save({"common/conanfile.py": GenConanfile("common", "1.0").with_settings("os"),
            "tool/conanfile.py": GenConanfile("tool", "1.0").with_settings("os")
                                                            .with_requires("common/1.0"),
            "lib/conanfile.py": GenConanfile("lib", "1.0").with_settings("os")
                                                          .with_requires("tool/1.0"),
            "consumer/conanfile.py":
                GenConanfile("consumer", "1.0").with_settings("os")
                                               .with_requires("lib/1.0")
                                               .with_build_requires("tool/1.0")})
    c.run("export common")
    c.run("export tool")
    c.run("export lib")
    # cross compile Linux->Windows
    c.run("lock create consumer/conanfile.py -s:h os=Linux -s:b os=Windows --build=*")
    print(c.load("consumer/conan.lock"))
    c.run("install --tool-requires=tool/1.0 --build=missing --lockfile=consumer/conan.lock ")
    print(c.out)
