import json
import textwrap

from conan.test.utils.tools import TestClient


def test_extended_cpp_info():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def package_info(self):
                self.cpp_info.libs = {"mylib": {"location": "my_custom_location",
                                                "type": "static-library"}}
            """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    settings = "-s os=Windows -s compiler=msvc -s compiler.version=191 -s arch=x86_64"
    c.run(f"install --requires=pkg/0.1 {settings} -g CPSDeps")
    pkg = json.loads(c.load("build/cps/msvc-191-x86_64-release/pkg.cps"))
    assert pkg["name"] == "pkg"
    assert pkg["version"] == "0.1"
    assert pkg["default_components"] == ["pkg"]
    pkg_comp = pkg["components"]["pkg"]
    assert pkg_comp["type"] == "archive"
    assert pkg_comp["location"] == "my_custom_location"
