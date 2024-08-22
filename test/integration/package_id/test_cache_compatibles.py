import os
import re
import textwrap

import pytest

from conan.test.utils.tools import TestClient, GenConanfile
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
        assert "dep/0.1: Main binary package '9e186f6d94c008b544af1569d1a6368d8339efc5' missing"\
               in client.out
        assert f"Found compatible package '{package_id}'" in client.out

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
    assert "dep/0.1: Main binary package 'ec174bec4a5ee2d44d3e33d9f4fdacd9b65a6772' missing" \
           in client.out
    assert f"Found compatible package '{package_id}'" in client.out

    client.run(f"install consumer {base_settings} -s build_type=Debug -s compiler.cppstd=17")
    assert "dep/0.1: Main binary package '94758b7bbcb365aaf355913b35431c0da6ed6da5' missing" \
           in client.out
    assert f"Found compatible package '{package_id}'" in client.out


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

    client.run(f"install consumer {base_settings} -s compiler.cppstd=17", assert_error=True)
    assert "dep/0.1: Invalid: Current cppstd (17) is lower than the required C++ standard (20)." \
           in client.out


def test_cppstd_server():
    """ this test proves the order, first from cache
    """
    c = TestClient(default_server_user=True)
    compatibles = textwrap.dedent("""\
        def compatibility(conanfile):
            return [{"settings": [("compiler.cppstd", v)]} for v in ("11", "14", "17", "20")]
        """)
    compatible_folder = os.path.join(c.cache.plugins_path, "compatibility")
    save(os.path.join(compatible_folder, "compatibility.py"), compatibles)

    conanfile = GenConanfile("dep", "0.1").with_settings("compiler")
    c.save({"dep/conanfile.py": conanfile,
            "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})

    base_settings = "-s compiler=gcc -s compiler.version=8 -s compiler.libcxx=libstdc++11"
    c.run(f"create dep {base_settings} -s compiler.cppstd=20")
    c.run("upload * -r=default -c")
    c.run("remove * -c")

    c.run(f"install consumer {base_settings} -s compiler.cppstd=17")
    assert "dep/0.1: Checking 3 compatible configurations" in c.out
    assert "dep/0.1: Compatible configurations not found in cache, checking servers" in c.out
    assert "dep/0.1: Main binary package '6179018ccb6b15e6443829bf3640e25f2718b931' missing" \
           in c.out
    assert "Found compatible package '326c500588d969f55133fdda29506ef61ef03eee': " \
           "compiler.cppstd=20" in c.out
    c.assert_listed_binary({"dep/0.1": ("326c500588d969f55133fdda29506ef61ef03eee",
                                        "Download (default)")})
    # second time, not download, already in cache
    c.run(f"install consumer {base_settings} -s compiler.cppstd=17")
    assert "dep/0.1: Checking 3 compatible configurations" in c.out
    assert "dep/0.1: Compatible configurations not found in cache, checking servers" not in c.out
    assert "dep/0.1: Main binary package '6179018ccb6b15e6443829bf3640e25f2718b931' missing" in c.out
    assert "Found compatible package '326c500588d969f55133fdda29506ef61ef03eee': " \
           "compiler.cppstd=20" in c.out
    c.assert_listed_binary({"dep/0.1": ("326c500588d969f55133fdda29506ef61ef03eee", "Cache")})

    # update checks in servers
    c2 = TestClient(servers=c.servers, inputs=["admin", "password"])
    c2.save({"dep/conanfile.py": conanfile})
    c2.run(f"create dep {base_settings} -s compiler.cppstd=14")
    c2.run("upload * -r=default -c")

    c.run(f"install consumer {base_settings} -s compiler.cppstd=17 --update")
    assert "dep/0.1: Checking 3 compatible configurations" in c.out
    assert "dep/0.1: Compatible configurations not found in cache, checking servers" not in c.out
    assert "dep/0.1: Main binary package '6179018ccb6b15e6443829bf3640e25f2718b931' missing" in c.out
    assert "Found compatible package 'ce92fac7c26ace631e30875ddbb3a58a190eb601': " \
           "compiler.cppstd=14" in c.out
    c.assert_listed_binary({"dep/0.1": ("ce92fac7c26ace631e30875ddbb3a58a190eb601",
                                        "Download (default)")})


class TestDefaultCompat:

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
        c.save({"conanfile.py": conanfile, "profile_build": "[settings]\nos=Windows\narch=x86_64"})
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
              f"-s compiler.runtime={runtime} -pr:b=profile_build")
        package_id1 = c.created_package_id("mylib/1.0")

        # Try to install with cppstd 14, it will find cppstd 17 as compatible
        c.run(f"install --requires=mylib/1.0@ -s os={os_} -s arch={arch} -s build_type={build_type} "
              f"-s compiler={compiler} "
              f"-s compiler.version={version} -s compiler.cppstd=14 "
              f"-s compiler.runtime={runtime} -pr:b=profile_build")
        assert "mylib/1.0: Main binary package 'e340edd75790e7156c595edebd3d98b10a2e091e' missing."\
               f"Using compatible package '{package_id1}'"

    def test_fail_with_options_deleted(self):
        """
        This test used to fail with "ConanException: option 'with_fmt_alias' doesn't exist",
        because it was removed by the package_id()
        """
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

        c.run("create . -s compiler.cppstd=14")

        c.run("create . --build=missing -s compiler.cppstd=17")
        assert "mylib/1.0: Main binary package" in c.out
        assert "Found compatible package" in c.out
        assert "Possible options are ['shared', 'header_only']" not in c.out
        assert "mylib/1.0: WARN: WITH_FMT_ALIAS=False" in c.out

    def test_header_only_build_missing(self):
        """
        this test failed with self.settings.compiler setting didn't exist
        """
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class SumConan(ConanFile):
                name = "sum"
                version = "0.1"
                settings = "os", "arch", "compiler", "build_type"
                def build(self):
                    self.output.warning("My compiler is '{}'".format(self.settings.compiler))
                def package_id(self):
                    self.info.clear()
        """)

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . -s compiler.cppstd=17 --build missing")
        client.assert_listed_binary({"sum/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Build")})
        # Just check that it works and doesn't fail
        assert "Installing packages" in client.out
        client.run("create . -s compiler.cppstd=14 --build missing")
        # Now it will not build, as package exist
        client.assert_listed_binary({"sum/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Cache")})
        assert "Installing packages" in client.out

    def test_check_min_cppstd(self):
        """ test that the check_min_cppstd works fine wiht compatibility, as it is based
        on ``conanfile.info.settings`` not ``conanfile.settings``
        """
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.build import check_min_cppstd, valid_min_cppstd
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "arch", "compiler", "build_type"
                def validate(self):
                    check_min_cppstd(self, "17", False)
                    self.output.info("valid standard!!")
                def package_info(self):
                    self.output.info("CPPSTD: {}".format(self.settings.compiler.cppstd))
            """)

        c = TestClient()
        c.save({"conanfile.py": conanfile})
        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++11"
        c.run(f"create .  {settings} -s compiler.cppstd=17")
        assert "pkg/0.1: valid standard!!" in c.out
        assert "pkg/0.1: CPPSTD: 17" in c.out
        c.run(f"install {settings} --requires=pkg/0.1 -s compiler.cppstd=14", assert_error=True)
        assert "pkg/0.1: Invalid: Current cppstd (14) is lower than the required C++ standard (17)."\
               in c.out
        c.run(f"install {settings} --requires=pkg/0.1 -s compiler.cppstd=20")
        assert "valid standard!!" in c.out
        assert "pkg/0.1: CPPSTD: 17" in c.out

    def test_check_min_cstd(self):
        """ test that the check_min_cstd works fine wiht compatibility
        """
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.build import check_min_cstd
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "arch", "compiler", "build_type"
                languages = "C"
                def validate(self):
                    check_min_cstd(self, "17", False)
                    self.output.info("valid standard!!")
                def package_info(self):
                    self.output.info("CSTD: {}".format(self.settings.compiler.cstd))
            """)

        c = TestClient()
        c.save({"conanfile.py": conanfile})
        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++11"
        c.run(f"create .  {settings} -s compiler.cstd=17")
        assert "pkg/0.1: valid standard!!" in c.out
        assert "pkg/0.1: CSTD: 17" in c.out
        c.run(f"install {settings} --requires=pkg/0.1 -s compiler.cstd=11", assert_error=True)
        assert "pkg/0.1: Invalid: Current cstd (11) is lower than the required C standard (17)."\
               in c.out
        c.run(f"install {settings} --requires=pkg/0.1 -s compiler.cstd=23")
        assert "valid standard!!" in c.out
        assert "pkg/0.1: CSTD: 17" in c.out

    def test_check_min_cppstd_interface(self):
        """ test that says that compatible binaries are ok, as long as the user defined
        cppstd>=14. The syntax is a bit forced, maybe we want to improve ``check_min_cppstd``
        capabilities to be able to raise ConanInvalidConfiguration too
        """
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            from conan.tools.build import check_min_cppstd, valid_min_cppstd
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "arch", "compiler", "build_type"
                def validate(self):
                    if int(str(self.info.settings.compiler.cppstd).replace("gnu", "")) <= 14:
                        raise ConanInvalidConfiguration("incompatible cppstd!")
                    check_min_cppstd(self, "17", False)  # based on self.info
                    self.output.info("valid standard!!")
                def package_info(self):
                    self.output.info("CPPSTD: {}".format(self.settings.compiler.cppstd))
            """)

        c = TestClient()
        c.save({"conanfile.py": conanfile})
        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++11"
        c.run(f"create .  {settings} -s compiler.cppstd=17")
        assert "pkg/0.1: valid standard!!" in c.out
        assert "pkg/0.1: CPPSTD: 17" in c.out
        c.run(f"install {settings} --requires=pkg/0.1 -s compiler.cppstd=14", assert_error=True)
        assert "valid standard!!" not in c.out
        assert "pkg/0.1: Invalid: incompatible cppstd!" in c.out
        c.run(f"install {settings} --requires=pkg/0.1 -s compiler.cppstd=20")
        assert "valid standard!!" in c.out
        assert "pkg/0.1: CPPSTD: 17" in c.out

    def test_can_create_multiple(self):
        c = TestClient()
        c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os", "arch", "compiler",
                                                                         "build_type")})
        settings = "-s os=Linux -s arch=x86_64 -s compiler=gcc -s compiler.version=9 "\
                   "-s compiler.libcxx=libstdc++11"
        c.run(f"create . {settings} -s compiler.cppstd=11")
        c.assert_listed_binary({"pkg/0.1": ("0d5f0b9d89187b4e62abb10ae409997e152db9de", "Build")})
        c.run(f"create . {settings} -s compiler.cppstd=14")
        c.assert_listed_binary({"pkg/0.1": ("145f423d315bee340546093be5b333ef5238668e", "Build")})
        c.run(f"create . {settings} -s compiler.cppstd=17")
        c.assert_listed_binary({"pkg/0.1": ("00fcbc3b6ab76a68f15e7e750e8081d57a6f5812", "Build")})

    def test_unnecessary_builds(self):
        # https://github.com/conan-io/conan/issues/15657
        c = TestClient()
        c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
                "dep/conanfile.py": GenConanfile("dep", "0.1").with_tool_requires("tool/0.1"),
                "app/conanfile.py": GenConanfile("app", "0.1").with_requires("dep/0.1")
                                                              .with_tool_requires("tool/0.1"),})
        c.run("create tool")
        c.run("create dep ")
        c.run("create app ")
        c.run("remove tool:* -c")
        c.run("install --requires=dep/0.1  --build=missing")
        assert re.search(r"Skipped binaries(\s*)tool/0.1", c.out)
        c.run("graph info --requires=app/0.1 --build=missing")
        assert re.search(r"Skipped binaries(\s*)tool/0.1", c.out)
        c.run("install --requires=app/0.1  --build=missing")
        assert re.search(r"Skipped binaries(\s*)tool/0.1", c.out)

    def test_msvc_194_fallback(self):
        c = TestClient()
        save(c.cache.default_profile_path, "")
        c.save({"conanfile.py": GenConanfile("mylib", "1.0").with_settings("os", "arch",
                                                                           "compiler", "build_type"),
                "profile_build": "[settings]\nos=Windows\narch=x86_64"})

        c.run("create . -s os=Windows -s arch=x86_64 -s build_type=Release "
              "-s compiler=msvc "
              "-s compiler.version=193 -s compiler.cppstd=17 "
              "-s compiler.runtime=dynamic -pr:b=profile_build")
        package_id1 = c.created_package_id("mylib/1.0")

        # Try to install with cppstd 14, it will find cppstd 17 as compatible
        c.run("install --requires=mylib/1.0@ -s os=Windows -s arch=x86_64 -s build_type=Release "
              "-s compiler=msvc "
              "-s compiler.version=194 -s compiler.cppstd=14 "
              "-s compiler.runtime=dynamic -pr:b=profile_build")
        assert "mylib/1.0: Main binary package 'e340edd75790e7156c595edebd3d98b10a2e091e' missing."\
               f"Using compatible package '{package_id1}'"

        c.run("install --requires=mylib/1.0@ -s os=Windows -s arch=x86_64 -s build_type=Release "
              "-s compiler=msvc "
              "-s compiler.version=194 -s compiler.cppstd=17 "
              "-s compiler.runtime=dynamic -pr:b=profile_build")
        assert "mylib/1.0: Main binary package 'e340edd75790e7156c595edebd3d98b10a2e091e' missing." \
               f"Using compatible package '{package_id1}'"


class TestErrorsCompatibility:
    """ when the plugin fails, we want a clear message and a helpful trace
    """
    def test_error_compatibility(self):
        c = TestClient()
        debug_compat = textwrap.dedent("""\
            def debug_compat(conanfile):
                other(conanfile)

            def other(conanfile):
                conanfile.settings.os
            """)
        compatibles = textwrap.dedent("""\
            from debug_compat import debug_compat
            def compatibility(conanfile):
                return debug_compat(conanfile)
            """)
        compatible_folder = os.path.join(c.cache.plugins_path, "compatibility")
        save(os.path.join(compatible_folder, "compatibility.py"), compatibles)
        save(os.path.join(compatible_folder, "debug_compat.py"), debug_compat)

        conanfile = GenConanfile("dep", "0.1")
        c.save({"dep/conanfile.py": conanfile,
                "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})

        c.run(f"export dep")
        c.run(f"install consumer", assert_error=True)
        assert "Error while processing 'compatibility.py' plugin for 'dep/0.1', line 3" in c.out
        assert "while calling 'debug_compat', line 2" in c.out
        assert "while calling 'other', line 5" in c.out

    def test_remove_plugin_file(self):
        c = TestClient()
        c.run("version")  # to trigger the creation
        os.remove(os.path.join(c.cache.plugins_path, "compatibility", "compatibility.py"))
        c.save({"conanfile.txt": ""})
        c.run("install .", assert_error=True)
        assert "ERROR: The 'compatibility.py' plugin file doesn't exist" in c.out
