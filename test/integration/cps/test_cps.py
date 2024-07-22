import json
import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_cps():
    c = TestClient()
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1").with_settings("build_type")
                                                          .with_class_attribute("license='MIT'")})
    c.run("create pkg")

    c.run("install --requires=pkg/0.1 -s arch=x86_64 -g CPSDeps")
    pkg = json.loads(c.load("pkg.cps"))
    print(json.dumps(pkg, indent=2))
    assert pkg["name"] == "pkg"
    assert pkg["version"] == "0.1"
    assert pkg["license"] == "MIT"
    assert pkg["configurations"] == ["release"]
    assert pkg["default_components"] == ["pkg"]
    pkg_comp = pkg["components"]["pkg"]
    assert pkg_comp["type"] == "unknown"
    mapping = json.loads(c.load("cpsmap-x86_64-Release.json"))
    for _, path_cps in mapping.items():
        assert os.path.exists(path_cps)


def test_cps_static_lib():
    c = TestClient()
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1").with_package_file("lib/pkg.a", "-")
                                                          .with_settings("build_type")
            .with_package_info(cpp_info={"libs": ["pkg"]}, env_info={})})
    c.run("create pkg")

    c.run("install --requires=pkg/0.1 -s arch=x86_64 -g CPSDeps")
    pkg = json.loads(c.load("pkg.cps"))
    print(json.dumps(pkg, indent=2))
    assert pkg["name"] == "pkg"
    assert pkg["version"] == "0.1"
    assert pkg["configurations"] == ["release"]
    assert pkg["default_components"] == ["pkg"]
    pkg_comp = pkg["components"]["pkg"]
    assert pkg_comp["type"] == "archive"
    assert pkg_comp["location"] is not None


def test_cps_in_pkg():
    c = TestClient()
    cps = textwrap.dedent("""
        {
          "cps_version": "0.8.1",
          "name": "pkg",
          "version": "0.1",
          "configurations": ["release"],
          "default-Components": ["pkg"],
          "components": {
            "pkg": { "type": "unknown", "definitions": ["mydefine"],
                     "includes": ["myinc"]}
          }
        }
        """)
    cps = "".join(cps.splitlines())
    conanfile = textwrap.dedent(f"""
        import os
        from conan.tools.files import save
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "mypkg"
            version = "0.1"

            def package(self):
                cps = '{cps}'
                cps_path = os.path.join(self.package_folder, "mypkg.cps")
                save(self, cps_path, cps)
        """)
    c.save({"pkg/conanfile.py": conanfile})
    c.run("create pkg")

    c.run("install --requires=mypkg/0.1 -s arch=x86_64 -g CPSDeps")
    print(c.out)

    mapping = json.loads(c.load("cpsmap-x86_64-Release.json"))
    print(json.dumps(mapping, indent=2))
    for _, path_cps in mapping.items():
        assert os.path.exists(path_cps)

    assert not os.path.exists(os.path.join(c.current_folder, "mypkg.cps"))

    c.run("install --requires=mypkg/0.1 -s arch=x86_64 -g CMakeDeps")
    print(c.out)
    cmake = c.load("mypkg-release-x86_64-data.cmake")
    print(cmake)
    assert 'set(mypkg_INCLUDE_DIRS_RELEASE "${mypkg_PACKAGE_FOLDER_RELEASE}/myinc")' in cmake
    assert 'set(mypkg_COMPILE_DEFINITIONS_RELEASE "mydefine")' in cmake
