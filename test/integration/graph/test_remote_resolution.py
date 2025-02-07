import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_build_requires_ranges():
    # app -> pkga ----------> pkgb ------------> pkgc
    #          \-cmake/[*]     \ -cmake/1.0        \-cmake/[*]
    # The resolution of cmake/[*] is invariant, it will always resolved to cmake/0.5, not
    # one to cmake/0.5 and the next one to cmake/1.0 because in between there was an explicit
    # dependency to cmake/1.0
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})

    client.run("create . --name=cmake --version=0.5")
    client.run("create . --name=cmake --version=1.0")
    client.run("upload cmake/1.0* -c -r default")
    client.run("remove cmake/1.0* -c")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            {}
            tool_requires = "cmake/{}"
            def generate(self):
                for r, d in self.dependencies.items():
                    self.output.info("REQUIRE {{}}: {{}}".format(r.ref, d))
                dep = self.dependencies.build.get("cmake")
                self.output.info("CMAKEVER: {{}}!!".format(dep.ref.version))
            """)
    client.save({"pkgc/conanfile.py": conanfile.format("", "[*]"),
                 "pkgb/conanfile.py": conanfile.format("requires = 'pkgc/1.0'", "1.0"),
                 "pkga/conanfile.py": conanfile.format("requires = 'pkgb/1.0'", "[*]"),
                 })
    client.run("export pkgc --name=pkgc --version=1.0")
    client.run("export pkgb --name=pkgb --version=1.0")
    client.run("export pkga --name=pkga --version=1.0")

    client.run("install --requires=pkga/1.0@ --build=missing")
    assert "pkgc/1.0: REQUIRE cmake/0.5: cmake/0.5" in client.out
    assert "pkgc/1.0: CMAKEVER: 0.5!!" in client.out
    assert "pkgb/1.0: REQUIRE cmake/1.0: cmake/1.0" in client.out
    assert "pkgb/1.0: CMAKEVER: 1.0!!" in client.out
    assert "pkga/1.0: REQUIRE cmake/0.5: cmake/0.5" in client.out
    assert "pkga/1.0: CMAKEVER: 0.5!!" in client.out
