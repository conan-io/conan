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

    settings = "-s os=Windows -s compiler=msvc -s compiler.version=191 -s arch=x86_64"
    c.run(f"install --requires=pkg/0.1 {settings} -g CPSDeps")
    pkg = json.loads(c.load("build/cps/msvc-191-x86_64-release/pkg.cps"))
    assert pkg["name"] == "pkg"
    assert pkg["version"] == "0.1"
    assert pkg["license"] == "MIT"
    assert pkg["configurations"] == ["release"]
    assert pkg["default_components"] == ["pkg"]
    pkg_comp = pkg["components"]["pkg"]
    assert pkg_comp["type"] == "interface"
    mapping = json.loads(c.load("build/cps/cpsmap-msvc-191-x86_64-release.json"))
    for _, path_cps in mapping.items():
        assert os.path.exists(path_cps)


def test_cps_static_lib():
    c = TestClient()
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1").with_package_file("lib/pkg.a", "-")
                                                          .with_settings("build_type")
            .with_package_info(cpp_info={"libs": ["pkg"]}, env_info={})})
    c.run("create pkg")

    settings = "-s os=Windows -s compiler=msvc -s compiler.version=191 -s arch=x86_64"
    c.run(f"install --requires=pkg/0.1 {settings} -g CPSDeps")
    pkg = json.loads(c.load("build/cps/msvc-191-x86_64-release/pkg.cps"))
    assert pkg["name"] == "pkg"
    assert pkg["version"] == "0.1"
    assert pkg["configurations"] == ["release"]
    assert pkg["default_components"] == ["pkg"]
    pkg_comp = pkg["components"]["pkg"]
    assert pkg_comp["type"] == "archive"
    assert pkg_comp["location"] is not None


def test_cps_header():
    c = TestClient()
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1").with_package_type("header-library")})
    c.run("create pkg")

    settings = "-s os=Windows -s compiler=msvc -s compiler.version=191 -s arch=x86_64"
    c.run(f"install --requires=pkg/0.1 {settings} -g CPSDeps")
    pkg = json.loads(c.load("build/cps/msvc-191-x86_64-release/pkg.cps"))
    assert pkg["name"] == "pkg"
    assert pkg["version"] == "0.1"
    assert "configurations" not in "pkg"
    assert pkg["default_components"] == ["pkg"]
    pkg_comp = pkg["components"]["pkg"]
    assert pkg_comp["type"] == "interface"
    assert "location" not in pkg_comp


def test_cps_in_pkg():
    c = TestClient()
    cps = textwrap.dedent("""\
        {
            "cps_version": "0.12.0",
            "name": "zlib",
            "version": "1.3.1",
            "configurations": ["release"],
            "default_components": ["zlib"],
            "components": {
                "zlib": {
                    "type": "archive",
                    "includes": ["@prefix@/include"],
                    "location": "@prefix@/lib/zlib.a"
                }
            }
        }
        """)
    cps = "".join(cps.splitlines())
    conanfile = textwrap.dedent(f"""
        import os
        from conan.tools.files import save
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "zlib"
            version = "1.3.1"

            def package(self):
                cps = '{cps}'
                cps_path = os.path.join(self.package_folder, "zlib.cps")
                save(self, cps_path, cps)

            def package_info(self):
                from conan.cps import CPS
                self.cpp_info = CPS.load("zlib.cps").to_conan()
        """)
    c.save({"pkg/conanfile.py": conanfile})
    c.run("create pkg")

    settings = "-s os=Windows -s compiler=msvc -s compiler.version=191 -s arch=x86_64"
    c.run(f"install --requires=zlib/1.3.1 {settings} -g CPSDeps")

    mapping = json.loads(c.load("build/cps/cpsmap-msvc-191-x86_64-release.json"))
    for _, path_cps in mapping.items():
        assert os.path.exists(path_cps)

    assert not os.path.exists(os.path.join(c.current_folder, "zlib.cps"))
    assert not os.path.exists(os.path.join(c.current_folder, "build", "cps", "zlib.cps"))

    c.run(f"install --requires=zlib/1.3.1 {settings} -g CMakeDeps")
    cmake = c.load("zlib-release-x86_64-data.cmake")
    assert 'set(zlib_INCLUDE_DIRS_RELEASE "${zlib_PACKAGE_FOLDER_RELEASE}/include")' in cmake
    assert 'set(zlib_LIB_DIRS_RELEASE "${zlib_PACKAGE_FOLDER_RELEASE}/lib")'
    assert 'set(zlib_LIBS_RELEASE zlib)' in cmake
