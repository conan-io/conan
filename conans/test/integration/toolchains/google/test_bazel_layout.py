import os
import textwrap

import pytest

from conan.tools.files import load
from conan.tools.google import BazelToolchain
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def conanfile():
    return textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelToolchain, bazel_layout
        class ExampleConanIntegration(ConanFile):
            settings = "os", "arch", "build_type", "compiler"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            generators = 'BazelToolchain'
            def layout(self):
                bazel_layout(self)
    """)


@pytest.mark.parametrize("generators_folder", [None, "other"])
def test_bazel_layout_generators_folder_conf(generators_folder, conanfile):
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=apple-clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=13.0
    os=Macos
    {}
    """)
    conf = textwrap.dedent("""
    [conf]
    tools.google.bazel_layout:generators_folder={}
    """)
    profile = profile.format("" if generators_folder is None else conf.format(generators_folder))
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr profile")
    # FIXME: "conan" is the default one in Conan 2.x
    # assert load(c, os.path.join(c.current_folder, generators_folder or "conan", BazelToolchain.bazelrc_name))
    assert load(c, os.path.join(c.current_folder, generators_folder or ".", BazelToolchain.bazelrc_name))
