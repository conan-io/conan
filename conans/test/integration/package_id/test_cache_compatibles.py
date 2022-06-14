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

        client.run("install consumer -s build_type=Debug")
        assert "dep/0.1: Main binary package '9e186f6d94c008b544af1569d1a6368d8339efc5' missing. "\
               f"Using compatible package '{package_id}'" in client.out

    def test_compatible_recipe_reference(self, client):
        """ check that the recipe name can be used to filter
        """
        client.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1").with_setting("build_type"),
                     "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")})

        client.run("create pkg -s build_type=Release")

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

    client.run(f"install consumer {base_settings} -s compiler.cppstd=17")
    assert "dep/0.1: Checking 3 compatible configurations" in client.out
    assert "dep/0.1: Main binary package 'ec174bec4a5ee2d44d3e33d9f4fdacd9b65a6772' missing. "\
           f"Using compatible package '{package_id}'" in client.out

    client.run(f"install consumer {base_settings} -s build_type=Debug -s compiler.cppstd=17")
    assert "dep/0.1: Main binary package '94758b7bbcb365aaf355913b35431c0da6ed6da5' missing. " \
           f"Using compatible package '{package_id}'" in client.out


def test_cppstd_validated():
    """ this test proves that 1 only configuration, the latest one, is tested and compatible,
    because the ``valiate()`` method is rejecting all cppstd<20
    """
    client = TestClient()
    compatibles = textwrap.dedent("""\
        def compatibility(conanfile):
            return [{"settings": [("compiler.cppstd", v)]} for v in ("11", "14", "17", "20")]
        """)
    compatible_folder = os.path.join(client.cache.plugins_path, "compatibility")
    save(os.path.join(compatible_folder, "compatibility.py"), compatibles)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.build import check_min_cppstd
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            settings = "compiler"
            def validate(self):
                check_min_cppstd(self, "20")
        """)

    client.save({"dep/conanfile.py": conanfile,
                 "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})

    base_settings = "-s compiler=gcc -s compiler.version=8 -s compiler.libcxx=libstdc++11"
    client.run(f"create dep {base_settings} -s compiler.cppstd=20")
    package_id = client.created_package_id("dep/0.1")

    client.run(f"install consumer {base_settings} -s compiler.cppstd=17")
    # This message here proves it, only 1 configuraton passed the check
    assert "dep/0.1: Checking 1 compatible configurations" in client.out
    assert "dep/0.1: Main binary package '6179018ccb6b15e6443829bf3640e25f2718b931' missing. "\
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
        version = "193"  # This is latest
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

    def test_default_app_compat_c(self):
        c = TestClient()
        save(c.cache.default_profile_path, "")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "app"
                version = "1.0"
                package_type = "application"
                settings = "os", "arch", "compiler", "build_type"

                def package_id(self):
                    try:  # This might not be defined if compiler=None
                        del self.info.settings.compiler.cppstd
                    except:
                        pass
            """)
        c.save({"conanfile.py": conanfile})
        os_ = "Windows"
        build_type = "Release"
        arch = "x86_64"
        compiler = "msvc"
        version = "193"
        cppstd = "14"
        runtime = "dynamic"
        c.run(f"create . -s os={os_} -s arch={arch} -s build_type={build_type} "
              f"-s compiler={compiler} "
              f"-s compiler.version={version} -s compiler.cppstd={cppstd} "
              f"-s compiler.runtime={runtime}")
        package_id1 = c.created_package_id("app/1.0")
        c.run(f"create . -s os={os_} -s arch={arch} -s build_type={build_type} "
              f"-s compiler={compiler} "
              f"-s compiler.version={version} -s compiler.cppstd=17 "
              f"-s compiler.runtime={runtime}")
        package_id2 = c.created_package_id("app/1.0")
        assert package_id1 == package_id2  # It does not depend on 'compiler.cppstd'

        c.run(f"install --requires=app/1.0@ -s os={os_} -s arch={arch}")
        assert "app/1.0: Main binary package 'e340edd75790e7156c595edebd3d98b10a2e091e' missing."\
               f"Using compatible package '{package_id1}'"

    def test_default_cppstd_compatibility(self):
        c = TestClient()
        save(c.cache.default_profile_path, "")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "mylib"
                version = "1.0"
                package_type = "library"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                settings = "os", "arch", "compiler", "build_type"
            """)
        c.save({"conanfile.py": conanfile})
        os_ = "Windows"
        build_type = "Release"
        arch = "x86_64"
        compiler = "msvc"
        version = "191"
        cppstd = "17"
        runtime = "dynamic"
        c.run(f"create . -s os={os_} -s arch={arch} -s build_type={build_type} "
              f"-s compiler={compiler} "
              f"-s compiler.version={version} -s compiler.cppstd={cppstd} "
              f"-s compiler.runtime={runtime}")
        package_id1 = c.created_package_id("mylib/1.0")

        # Try to install with cppstd 14, it will find cppstd 17 as compatible
        c.run(f"install --requires=mylib/1.0@ -s os={os_} -s arch={arch} -s build_type={build_type} "
              f"-s compiler={compiler} "
              f"-s compiler.version={version} -s compiler.cppstd=14 "
              f"-s compiler.runtime={runtime}")
        assert "mylib/1.0: Main binary package 'e340edd75790e7156c595edebd3d98b10a2e091e' missing."\
               f"Using compatible package '{package_id1}'"

    def test_fail_with_options_deleted(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "mylib"
                version = "1.0"

                options = {"with_fmt_alias": [True, False]}
                default_options = {"with_fmt_alias": False}

                settings = "os", "arch", "compiler", "build_type"

                def package_id(self):
                    del self.info.options.with_fmt_alias

                def package_info(self):
                    self.output.warning("WITH_FMT_ALIAS={}".format(self.options.with_fmt_alias))
            """)
        c.save({"conanfile.py": conanfile})

        c.run("create . --build=missing -s compiler.cppstd=17")
        assert "Possible options are ['shared', 'header_only']" not in c.out
