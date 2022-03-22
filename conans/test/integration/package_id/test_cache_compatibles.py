import os
import textwrap

import pytest

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class TestCacheCompatibles:
    @pytest.fixture()
    def client(self):
        client = TestClient()
        debug_compat = textwrap.dedent("""\
            def debug_compat(conanfile):
                result = []
                if conanfile.settings.build_type == "Debug":
                    result.append({"settings": [("build_type", "Release")]})
                return result
            """)
        compatibles = textwrap.dedent("""\
            from debug_compat import debug_compat
            def compatibility(conanfile):
                if conanfile.name != "dep":
                    return
                return debug_compat(conanfile)
            """)
        compatible_folder = os.path.join(client.cache.plugins_path, "compatibility")
        save(os.path.join(compatible_folder, "compatibility.py"), compatibles)
        save(os.path.join(compatible_folder, "debug_compat.py"), debug_compat)
        return client

    def test_compatible_build_type(self, client):
        client.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_setting("build_type"),
                     "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})

        client.run("create dep -s build_type=Release")
        package_id = client.created_package_id("dep/0.1")
        assert f"dep/0.1: Package '{package_id}' created" in client.out

        client.run("install consumer -s build_type=Debug")
        assert "dep/0.1: Main binary package '040ce2bd0189e377b2d15eb7246a4274d1c63317' missing. "\
               f"Using compatible package '{package_id}'" in client.out

    def test_compatible_recipe_reference(self, client):
        """ check that the recipe name can be used to filter
        """
        client.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1").with_setting("build_type"),
                     "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")})

        client.run("create pkg -s build_type=Release")
        pkg_package_id = client.created_package_id("pkg/0.1")
        assert f"pkg/0.1: Package '{pkg_package_id}' created" in client.out

        # The compatibility doesn't fire for package "pkg"
        client.run("install consumer -s build_type=Debug", assert_error=True)
        assert "ERROR: Missing binary" in client.out


def test_cppstd():
    client = TestClient()
    compatibles = textwrap.dedent("""\
        def compatibility(conanfile):
            cppstd = conanfile.settings.get_safe("compiler.cppstd")
            if not cppstd:
                return

            result = []
            for cppstd in ["11", "14", "17", "20"]:
                result.append({"settings": [("compiler.cppstd", cppstd)]})

            if conanfile.settings.build_type == "Debug":
                for cppstd in ["11", "14", "17", "20"]:
                    result.append({"settings": [("compiler.cppstd", cppstd),
                                                ("build_type", "Release")]})
            return result
        """)
    compatible_folder = os.path.join(client.cache.plugins_path, "compatibility")
    save(os.path.join(compatible_folder, "compatibility.py"), compatibles)

    conanfile = GenConanfile("dep", "0.1").with_settings("compiler", "build_type")
    client.save({"dep/conanfile.py": conanfile,
                 "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})

    base_settings = "-s compiler=gcc -s compiler.version=7 -s compiler.libcxx=libstdc++11"
    client.run(f"create dep {base_settings} -s build_type=Release -s compiler.cppstd=14")
    package_id = client.created_package_id("dep/0.1")
    assert f"dep/0.1: Package '{package_id}' created" in client.out

    client.run(f"install consumer {base_settings} -s compiler.cppstd=17")
    assert "dep/0.1: Main binary package '24697c4fc0c8af2b85b468de52e6d5323c4b4f0d' missing. "\
           f"Using compatible package '{package_id}'" in client.out

    client.run(f"install consumer {base_settings} -s build_type=Debug -s compiler.cppstd=17")
    assert "dep/0.1: Main binary package 'c3d18617551d2975da867453ee96f409034f1365' missing. " \
           f"Using compatible package '{package_id}'" in client.out


class TestDefaultCompat:

    def test_default_app_compat(self):
        c = TestClient()
        save(c.cache.default_profile_path, "")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "app"
                version = "1.0"
                package_type = "application"
                settings = "os", "arch", "compiler", "build_type"
            """)
        c.save({"conanfile.py": conanfile})
        os_ = "Windows"
        build_type = "Release"
        arch = "x86_64"
        compiler = "msvc"
        version = "191"
        cppstd = "14"
        runtime = "dynamic"
        c.run(f"create . -s os={os_} -s arch={arch} -s build_type={build_type} "
              f"-s compiler={compiler} "
              f"-s compiler.version={version} -s compiler.cppstd={cppstd} "
              f"-s compiler.runtime={runtime}")
        package_id = c.created_package_id("app/1.0")
        c.run(f"install --requires=app/1.0@ -s os={os_} -s arch={arch}")
        assert "app/1.0: Main binary package 'e340edd75790e7156c595edebd3d98b10a2e091e' missing."\
               f"Using compatible package '{package_id}'"
