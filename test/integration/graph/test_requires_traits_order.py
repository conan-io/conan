import json
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("requires", ["lib_b/1.0\nlib_a/1.0", "lib_a/1.0\nlib_b/1.0"])
def test_diamond_header_library_libs_trait_order(requires):
    # https://github.com/conan-io/conan/issues/20447
    c = TestClient(light=True)
    c.save({"lib_a/conanfile.py": GenConanfile("lib_a", "1.0").with_package_type("header-library"),
            "lib_b/conanfile.py": GenConanfile("lib_b", "1.0").with_package_type("header-library")
                                                              .with_requires("lib_a/1.0"),
            "conanfile.txt": f"[requires]\n{requires}"})
    c.run("export lib_a")
    c.run("export lib_b")
    c.run("graph info . --format=json")
    nodes = json.loads(c.stdout)["graph"]["nodes"]
    consumer_deps = nodes["0"]["dependencies"]
    lib_a_req = next(d for d in consumer_deps.values() if d["ref"].startswith("lib_a/1.0"))
    assert lib_a_req["direct"] is True
    assert lib_a_req["libs"] is False


@pytest.mark.parametrize("a_type", ["application", "shared-library", "static-library",
                                    "header-library", "build-scripts"])
@pytest.mark.parametrize("b_type", ["static-library", "header-library", "shared-library"])
def test_diamond_traits_independent_of_order(a_type, b_type):
    # The traits of the direct dependency do not depend on the order of the requires
    c = TestClient(light=True)
    c.save({"lib_a/conanfile.py": GenConanfile("lib_a", "1.0").with_package_type(a_type),
            "lib_b/conanfile.py": GenConanfile("lib_b", "1.0").with_package_type(b_type)
                                                              .with_requires("lib_a/1.0")})
    c.run("export lib_a")
    c.run("export lib_b")
    traits = []
    for requires in ("lib_b/1.0\nlib_a/1.0", "lib_a/1.0\nlib_b/1.0"):
        c.save({"conanfile.txt": f"[requires]\n{requires}"})
        c.run("graph info . --format=json")
        deps = json.loads(c.stdout)["graph"]["nodes"]["0"]["dependencies"]
        lib_a = next(d for d in deps.values() if d["ref"].startswith("lib_a/1.0"))
        traits.append({k: v for k, v in lib_a.items() if k not in ("ref", "require")})
    assert traits[0] == traits[1]


@pytest.mark.parametrize("a_type", ["application", "header-library", "static-library"])
@pytest.mark.parametrize("traits", ["libs=True", "headers=True", "libs=True, headers=True",
                                    "headers=False", "libs=False", "run=True"])
def test_diamond_explicit_traits_independent_of_order(a_type, traits):
    # Traits explicitly defined in the direct requires() do not depend on the order either
    c = TestClient(light=True)
    c.save({"lib_a/conanfile.py": GenConanfile("lib_a", "1.0").with_package_type(a_type),
            "lib_b/conanfile.py": GenConanfile("lib_b", "1.0").with_package_type("header-library")
                                                              .with_requires("lib_a/1.0")})
    c.run("export lib_a")
    c.run("export lib_b")
    result = []
    lines = ["self.requires('lib_b/1.0')", f"self.requires('lib_a/1.0', {traits})"]
    for order in (lines, lines[::-1]):
        consumer = textwrap.dedent(f"""
            from conan import ConanFile
            class Pkg(ConanFile):
                def requirements(self):
                    {order[0]}
                    {order[1]}
            """)
        c.save({"conanfile.py": consumer})
        c.run("graph info . --format=json")
        deps = json.loads(c.stdout)["graph"]["nodes"]["0"]["dependencies"]
        lib_a = next(d for d in deps.values() if d["ref"].startswith("lib_a/1.0"))
        result.append({k: v for k, v in lib_a.items() if k not in ("ref", "require")})
    assert result[0] == result[1]
