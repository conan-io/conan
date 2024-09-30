import json
import textwrap
import unittest

from conan.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class CompatibleIDsTest(unittest.TestCase):

    def test_compatible_setting(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def compatibility(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        return [{"settings": [("compiler.version", v)]}
                                for v in ("4.8", "4.7", "4.6")]

                def package_info(self):
                    self.output.info("PackageInfo!: Gcc version: %s!"
                                     % self.settings.compiler.version)
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        # Create package with gcc 4.8
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable -pr=myprofile -s compiler.version=4.8")
        package_id = client.created_package_id("pkg/0.1@user/stable")

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.8!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def test_compatible_setting_no_binary(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile

           class Pkg(ConanFile):
               settings = "os", "compiler"
               def compatibility(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        return [{"settings": [("compiler.version", v)]}
                                for v in ("4.8", "4.7", "4.6")]
               def package_info(self):
                   self.output.info("PackageInfo!: Gcc version: %s!"
                                    % self.settings.compiler.version)
           """)
        profile = textwrap.dedent("""
           [settings]
           os = Linux
           compiler=gcc
           compiler.version=4.9
           compiler.libcxx=libstdc++
           """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        # Create package with gcc 4.8
        client.run("export . --name=pkg --version=0.1 --user=user --channel=stable")
        self.assertIn("pkg/0.1@user/stable: Exported: "
                      "pkg/0.1@user/stable#d165eb4bcdd1c894a97d2a212956f5fe", client.out)
        client.run("export . --name=lib --version=0.1 --user=user --channel=stable")

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        client.save({"conanfile.py": GenConanfile().with_requires("pkg/0.1@user/stable", "lib/0.1@user/stable")})
        # No fallback
        client.run("install . -pr=myprofile --build=missing -u=lib")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.9!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable":
                                     ("1ded27c9546219fbd04d4440e05b2298f8230047", "Build")})
        assert "lib/0.1@user/stable: Compatible configurations not found in cache, checking servers" not in client.out
        assert "pkg/0.1@user/stable: Compatible configurations not found in cache, checking servers" in client.out

    def test_compatible_setting_no_user_channel(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def compatibility(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        return [{"settings": [("compiler.version", v)]}
                                for v in ("4.8", "4.7", "4.6")]
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        # No user/channel
        client.run("create . --name=pkg --version=0.1 -pr=myprofile -s compiler.version=4.8")
        package_id = client.created_package_id("pkg/0.1")

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        client.run("install . -pr=myprofile")
        client.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})
        self.assertIn("pkg/0.1: Already installed!", client.out)

    def test_compatible_option(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                options = {"optimized": [1, 2, 3]}
                default_options = {"optimized": 1}

                def compatibility(self):
                    return [{"options": [("optimized", v)]}
                            for v in range(int(self.options.optimized), 0, -1)]

                def package_info(self):
                    self.output.info("PackageInfo!: Option optimized %s!"
                                     % self.options.optimized)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable")
        package_id = client.created_package_id("pkg/0.1@user/stable")
        self.assertIn(f"pkg/0.1@user/stable: Package '{package_id}' created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("install . -o pkg/*:optimized=2 -vv")
        # Information messages
        missing_id = "0a8157f8083f5ece34828d27fb2bf5373ba26366"
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Option optimized 1!", client.out)
        self.assertIn("pkg/0.1@user/stable: Compatible package ID "
                      f"{missing_id} equal to the default package ID",
                      client.out)
        self.assertIn(f"pkg/0.1@user/stable: Main binary package '{missing_id}' missing", client.out)
        self.assertIn(f"Found compatible package '{package_id}'", client.out)
        # checking the resulting dependencies
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        client.run("install . -o pkg/*:optimized=3")
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def test_package_id_consumers(self):
        # If we fallback to a different binary upstream and we are using a "package_revision_mode"
        # the current package should have a different binary package ID too.
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler"
                def compatibility(self):
                    return [{"settings": [("compiler.version", "4.8")]}]
                def package_info(self):
                    self.output.info("PackageInfo!: Gcc version: %s!"
                                     % self.settings.compiler.version)
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        save(client.cache.new_config_path,
             "core.package_id:default_unknown_mode=recipe_revision_mode")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        # Create package with gcc 4.8
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable "
                   "-pr=myprofile -s compiler.version=4.8")
        package_id = client.created_package_id("pkg/0.1@user/stable")
        self.assertIn(f"pkg/0.1@user/stable: Package '{package_id}'"
                      " created", client.out)

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.8!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        consumer_id = "96465a24a53766aaac28e270d196db295e2fd22a"
        client.assert_listed_binary({"consumer/0.1@user/stable": (consumer_id, "Build")})
        self.assertIn(f"consumer/0.1@user/stable: Package '{consumer_id}' created", client.out)

        # Create package with gcc 4.9
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable -pr=myprofile")
        package_id = "1ded27c9546219fbd04d4440e05b2298f8230047"
        self.assertIn(f"pkg/0.1@user/stable: Package '{package_id}'"
                      f" created", client.out)

        # Consume it
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.9!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable": (f"{package_id}", "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        consumer_id = "41bc915fa380e9a046aacbc21256fcb46ad3179d"
        client.assert_listed_binary({"consumer/0.1@user/stable": (consumer_id, "Build")})
        self.assertIn(f"consumer/0.1@user/stable: Package '{consumer_id}' created", client.out)

    def test_build_missing(self):
        # https://github.com/conan-io/conan/issues/6133
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Conan(ConanFile):
                settings = "os"

                def compatibility(self):
                    if self.settings.os == "Windows":
                        return [{"settings": [("os", "Linux")]}]
                """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux")
        package_id = client.created_package_id("pkg/0.1@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("install . -s os=Windows --build=missing")
        client.assert_listed_binary({"pkg/0.1@user/testing": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/testing: Already installed!", client.out)

    def test_compatible_package_python_requires(self):
        # https://github.com/conan-io/conan/issues/6609
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=tool --version=0.1")
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Conan(ConanFile):
                settings = "os"
                python_requires = "tool/0.1"

                def compatibility(self):
                    if self.settings.os == "Windows":
                        return [{"settings": [("os", "Linux")]}]
                """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux")
        package_id = client.created_package_id("pkg/0.1@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("install . -s os=Windows")
        client.assert_listed_binary({"pkg/0.1@user/testing": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/testing: Already installed!", client.out)

    def test_compatible_lockfile(self):
        # https://github.com/conan-io/conan/issues/9002
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                def compatibility(self):
                    if self.settings.os == "Windows":
                        return [{"settings": [("os", "Linux")]}]
                def package_info(self):
                    self.output.info("PackageInfo!: OS: %s!" % self.settings.os)
            """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 -s os=Linux")
        self.assertIn("pkg/0.1: PackageInfo!: OS: Linux!", client.out)
        self.assertIn("pkg/0.1: Package '9a4eb3c8701508aa9458b1a73d0633783ecc2270' built",
                      client.out)

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        client.run("lock create . -s os=Windows --lockfile-out=deps.lock")
        client.run("install . -s os=Windows --lockfile=deps.lock")
        self.assertIn("pkg/0.1: PackageInfo!: OS: Linux!", client.out)
        self.assertIn("9a4eb3c8701508aa9458b1a73d0633783ecc2270", client.out)
        self.assertIn("pkg/0.1: Already installed!", client.out)

    def test_compatible_diamond(self):
        # https://github.com/conan-io/conan/issues/9880
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                {}
                settings = "build_type"
                def compatibility(self):
                    if self.settings.build_type == "Debug":
                       return [{{"settings": [("build_type", "Release")]}}]
                """)

        private = """def requirements(self):
        self.requires("pkga/0.1", visible=False)
        """
        client.save({"pkga/conanfile.py": conanfile.format(""),
                     "pkgb/conanfile.py": conanfile.format(private),
                     "pkgc/conanfile.py": conanfile.format('requires = "pkga/0.1"'),
                     "pkgd/conanfile.py": conanfile.format('requires = "pkgb/0.1", "pkgc/0.1"')
                     })
        client.run("create pkga --name=pkga --version=0.1 -s build_type=Release")
        client.run("create pkgb --name=pkgb --version=0.1 -s build_type=Release")
        client.run("create pkgc --name=pkgc --version=0.1 -s build_type=Release")

        client.run("install pkgd -s build_type=Debug")
        client.assert_listed_binary({"pkga/0.1":
                                    ("efa83b160a55b033c4ea706ddb980cd708e3ba1b", "Cache")})


class TestNewCompatibility:

    def test_compatible_setting(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "compiler"

                def compatibility(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        return [{"settings": [("compiler.version", v)]}
                                for v in ("4.8", "4.7", "4.6")]

                def package_info(self):
                    self.output.info("PackageInfo!: Gcc version: %s!"
                                     % self.settings.compiler.version)
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        c.save({"conanfile.py": conanfile,
                "myprofile": profile})
        # Create package with gcc 4.8
        c.run("create .  -pr=myprofile -s compiler.version=4.8")
        package_id = "c0c95d81351786c6c1103566a27fb1c1f78629ac"
        assert f"pkg/0.1: Package '{package_id}' created" in c.out

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        c.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        c.run("install . -pr=myprofile")
        assert "pkg/0.1: PackageInfo!: Gcc version: 4.8!" in c.out
        c.assert_listed_binary({"pkg/0.1": (f"{package_id}", "Cache")})
        assert "pkg/0.1: Already installed!" in c.out

    def test_compatibility_remove_package_id(self):
        # https://github.com/conan-io/conan/issues/13727
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class PdfiumConan(ConanFile):
                name = "pdfium"
                version = "2020.9"
                settings = "os", "compiler", "arch", "build_type"
                build_policy = "never"

                def compatibility(self):
                    result = []
                    if self.info.settings.build_type == "Debug":
                        result.append({"settings": [("build_type", "Release")]})
                    return result

                def package_id(self):
                    del self.info.settings.compiler.runtime
                    del self.info.settings.compiler.runtime_type
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Windows
            compiler=msvc
            compiler.version=192
            compiler.runtime=dynamic
            build_type=Release
            arch=x86_64
            """)
        c.save({"conanfile.py": conanfile,
                "myprofile": profile})
        c.run("create .  -pr=myprofile", assert_error=True)
        assert "ERROR: This package cannot be created, 'build_policy=never', " \
               "it can only be 'export-pkg'" in c.out
        c.run("export-pkg . -pr=myprofile")
        c.run("list pdfium/2020.9:*")

        c.run("install --requires=pdfium/2020.9 -pr=myprofile -s build_type=Debug")
        assert "Found compatible package" in c.out

    def test_compatibility_erase_package_id(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class PdfiumConan(ConanFile):
                name = "diligent-core"
                version = "1.0"
                settings = "compiler"
                options = {"foo": ["no"]}

                def package_id(self):
                    self.info.settings.compiler.runtime = "foobar"
                    self.info.options.foo = "yes"
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Windows
            compiler=msvc
            compiler.version=192
            compiler.runtime=dynamic
            build_type=Release
            arch=x86_64
            """)
        c.save({"conanfile.py": conanfile,
                "myprofile": profile})

        c.run("create . -pr:a=myprofile -s compiler.cppstd=20")
        c.run("install --requires=diligent-core/1.0 -pr:a=myprofile -s compiler.cppstd=17")
        assert "ERROR: Invalid setting 'foobar' is not a valid 'settings.compiler.runtime' value." not in c.out

    def test_compatibility_msvc_and_cppstd(self):
        """msvc 194 would not find compatible packages built with same version but different cppstd
        due to an issue in the msvc fallback compatibility rule."""
        tc = TestClient()
        profile = textwrap.dedent("""
                   [settings]
                   compiler=msvc
                   compiler.version=194
                   compiler.runtime=dynamic
                   """)
        tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_setting("compiler"),
                 "conanfile.py": GenConanfile("app", "1.0").with_require("dep/1.0").with_setting("compiler"),
                 "profile": profile})

        tc.run("create dep -pr=profile -s compiler.cppstd=20")
        tc.run("create . -pr=profile -s compiler.cppstd=17")
        tc.assert_listed_binary({"dep/1.0": ("b6d26a6bc439b25b434113982791edf9cab4d004", "Cache")})


class TestCompatibleBuild:
    def test_build_compatible(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.build import check_min_cppstd

           class Pkg(ConanFile):
               name = "pkg"
               version = "0.1"
               settings = "os", "compiler"

               def validate(self):
                   check_min_cppstd(self, 14)
            """)
        c.save({"conanfile.py": conanfile})
        settings = "-s os=Windows -s compiler=gcc -s compiler.version=11 " \
                   "-s compiler.libcxx=libstdc++11 -s compiler.cppstd=11"
        c.run(f"create . {settings}", assert_error=True)
        c.assert_listed_binary({"pkg/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid")})
        assert "pkg/0.1: Invalid: Current cppstd (11)" in c.out

        c.run(f"create . {settings} --build=compatible:&")
        # the one for cppstd=14 is built!!
        c.assert_listed_binary({"pkg/0.1": ("389803bed06200476fcee1af2023d4e9bfa24ff9", "Build")})
        c.run("list *:*")
        assert "compiler.cppstd: 14" in c.out

    def test_build_compatible_cant_build(self):
        # requires c++17 to build, can be consumed with c++14
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.build import check_min_cppstd

           class Pkg(ConanFile):
               name = "pkg"
               version = "0.1"
               settings = "os", "compiler"

               def validate(self):
                   check_min_cppstd(self, 14)

               def validate_build(self):
                   check_min_cppstd(self, 17)
            """)
        c.save({"conanfile.py": conanfile})
        settings = "-s os=Windows -s compiler=gcc -s compiler.version=11 " \
                   "-s compiler.libcxx=libstdc++11  -s compiler.cppstd=11"
        c.run(f"create . {settings}", assert_error=True)
        c.assert_listed_binary({"pkg/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid")})
        assert "pkg/0.1: Invalid: Current cppstd (11)" in c.out

        c.run(f"create . {settings} --build=missing", assert_error=True)
        c.assert_listed_binary({"pkg/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid")})
        assert "pkg/0.1: Invalid: Current cppstd (11)" in c.out

        c.run(f"create . {settings} --build=compatible:&")
        # the one for cppstd=17 is built!!
        c.assert_listed_binary({"pkg/0.1": ("58fb8ac6c2dc3e3f837253ce1a6ea59011525866", "Build")})
        c.run("list *:*")
        assert "compiler.cppstd: 17" in c.out

    def test_build_compatible_cant_build2(self):
        # requires c++17 to build, can be consumed with c++11
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.build import check_min_cppstd

           class Pkg(ConanFile):
               name = "pkg"
               version = "0.1"
               settings = "os", "compiler"

               def validate(self):
                   check_min_cppstd(self, 11)

               def validate_build(self):
                   check_min_cppstd(self, 17)
            """)
        c.save({"conanfile.py": conanfile})
        settings = "-s os=Windows -s compiler=gcc -s compiler.version=11 " \
                   "-s compiler.libcxx=libstdc++11  -s compiler.cppstd=11"
        c.run(f"create . {settings}", assert_error=True)
        c.assert_listed_binary({"pkg/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid")})
        assert "pkg/0.1: Cannot build for this configuration: Current cppstd (11)" in c.out

        c.run(f"create . {settings} --build=missing", assert_error=True)
        # the one for cppstd=17 is built!!
        c.assert_listed_binary({"pkg/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid")})
        assert "pkg/0.1: Cannot build for this configuration: Current cppstd (11)" in c.out

        c.run(f"create . {settings} --build=compatible:&")
        # the one for cppstd=17 is built!!
        c.assert_listed_binary({"pkg/0.1": ("58fb8ac6c2dc3e3f837253ce1a6ea59011525866", "Build")})
        c.run("list *:*")
        assert "compiler.cppstd: 17" in c.out

    def test_build_compatible_cant_build_only(self):
        # requires c++17 to build, but don't specify consumption
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.build import check_min_cppstd

           class Pkg(ConanFile):
               name = "pkg"
               version = "0.1"
               settings = "os", "compiler"

               def validate_build(self):
                   check_min_cppstd(self, 17)
            """)
        c.save({"conanfile.py": conanfile})
        settings = "-s os=Windows -s compiler=gcc -s compiler.version=11 " \
                   "-s compiler.libcxx=libstdc++11  -s compiler.cppstd=11"
        c.run(f"create . {settings}", assert_error=True)
        c.assert_listed_binary({"pkg/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid")})
        assert "pkg/0.1: Cannot build for this configuration: Current cppstd (11)" in c.out

        c.run(f"create . {settings} --build=missing", assert_error=True)
        # the one for cppstd=17 is built!!
        c.assert_listed_binary({"pkg/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid")})
        assert "pkg/0.1: Cannot build for this configuration: Current cppstd (11)" in c.out

        c.run(f"create . {settings} --build=compatible:&")
        # the one for cppstd=17 is built!!
        c.assert_listed_binary({"pkg/0.1": ("58fb8ac6c2dc3e3f837253ce1a6ea59011525866", "Build")})
        c.run("list *:*")
        assert "compiler.cppstd: 17" in c.out

    def test_multi_level_build_compatible(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.build import check_min_cppstd

           class Pkg(ConanFile):
               name = "{name}"
               version = "0.1"
               settings = "os", "compiler"
               {requires}

               def validate(self):
                   check_min_cppstd(self, {cppstd})
            """)
        c.save({"liba/conanfile.py": conanfile.format(name="liba", cppstd=14, requires=""),
                "libb/conanfile.py": conanfile.format(name="libb", cppstd=17,
                                                      requires='requires="liba/0.1"')})
        c.run("export liba")
        c.run("export libb")
        settings = "-s os=Windows -s compiler=gcc -s compiler.version=11 " \
                   "-s compiler.libcxx=libstdc++11 -s compiler.cppstd=11"
        c.run(f"install --requires=libb/0.1 {settings}", assert_error=True)
        c.assert_listed_binary({"liba/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Invalid"),
                                "libb/0.1": ("144910d65b27bcbf7d544201f5578555bbd0376e", "Invalid")})
        assert "liba/0.1: Invalid: Current cppstd (11)" in c.out
        assert "libb/0.1: Invalid: Current cppstd (11)" in c.out

        c.run(f"install --requires=libb/0.1 {settings} --build=compatible")
        # the one for cppstd=14 is built!!
        c.assert_listed_binary({"liba/0.1": ("389803bed06200476fcee1af2023d4e9bfa24ff9", "Build"),
                                "libb/0.1": ("8f29f49be3ba2b6cbc9fa1e05432ce928b96ae5d", "Build")})
        c.run("list liba:*")
        assert "compiler.cppstd: 14" in c.out
        c.run("list libb:*")
        assert "compiler.cppstd: 17" in c.out

    def test_multi_level_build_compatible_build_order(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.build import check_min_cppstd

           class Pkg(ConanFile):
               name = "{name}"
               version = "0.1"
               settings = "os", "compiler"
               {requires}

               def validate_build(self):
                   check_min_cppstd(self, {cppstd})
            """)
        c.save({"liba/conanfile.py": conanfile.format(name="liba", cppstd=14, requires=""),
                "libb/conanfile.py": conanfile.format(name="libb", cppstd=17,
                                                      requires='requires="liba/0.1"')})
        c.run("export liba")
        c.run("export libb")
        settings = "-s os=Windows -s compiler=gcc -s compiler.version=11 " \
                   "-s compiler.libcxx=libstdc++11 -s compiler.cppstd=11"
        c.run(f"graph build-order --requires=libb/0.1 {settings} --format=json", assert_error=True,
              redirect_stdout="build_order.json")
        c.assert_listed_binary({"liba/0.1": ("bb33db23c961978d08dc0cdd6bc786b45b3e5943", "Missing"),
                                "libb/0.1": ("144910d65b27bcbf7d544201f5578555bbd0376e", "Missing")})

        c.run(f"graph build-order --requires=libb/0.1 {settings} --build=compatible "
              "--order-by=configuration --format=json", redirect_stdout="build_order.json")
        bo = json.loads(c.load("build_order.json"))
        liba = bo["order"][0][0]
        assert liba["ref"] == "liba/0.1#c1459d256a9c2d3c49d149fd7c43310c"
        assert liba["info"]["compatibility_delta"] == {"settings": [["compiler.cppstd", "14"]]}
        assert liba["build_args"] == "--requires=liba/0.1 --build=compatible:liba/0.1"
        # Lets make sure the build works too
        c.run(f"install {settings} {liba['build_args']}")
        libb = bo["order"][1][0]
        assert libb["ref"] == "libb/0.1#62bb167aaa5306d1ac757bb817797f9e"
        assert libb["info"]["compatibility_delta"] == {"settings": [["compiler.cppstd", "17"]]}
        assert libb["build_args"] == "--requires=libb/0.1 --build=compatible:libb/0.1"
        # Lets make sure the build works too
        c.run(f"install {settings} {libb['build_args']}")

        # Now lets make sure that build-order-merge works too
        c.run(f"graph build-order --requires=libb/0.1 {settings} -s compiler.version=12 "
              "--build=compatible --order-by=configuration --format=json",
              redirect_stdout="build_order2.json")

        c.run(f"graph build-order-merge --file=build_order.json --file=build_order2.json -f=json",
              redirect_stdout="build_order_merged.json")
        bo = json.loads(c.load("build_order_merged.json"))
        for pkg_index in (0, 1):
            liba = bo["order"][0][pkg_index]
            assert liba["ref"] == "liba/0.1#c1459d256a9c2d3c49d149fd7c43310c"
            assert liba["info"]["compatibility_delta"] == {"settings": [["compiler.cppstd", "14"]]}
            assert liba["build_args"] == "--requires=liba/0.1 --build=compatible:liba/0.1"

        # By recipe also works
        c.run("remove *:* -c")
        c.run(f"graph build-order --requires=libb/0.1 {settings} --build=compatible "
              "--order-by=recipe --format=json", redirect_stdout="build_order.json")
        bo = json.loads(c.load("build_order.json"))
        liba = bo["order"][0][0]
        assert liba["ref"] == "liba/0.1#c1459d256a9c2d3c49d149fd7c43310c"
        pkga = liba["packages"][0][0]
        assert pkga["info"]["compatibility_delta"] == {"settings": [["compiler.cppstd", "14"]]}
        assert pkga["build_args"] == "--requires=liba/0.1 --build=compatible:liba/0.1"
        libb = bo["order"][1][0]
        assert libb["ref"] == "libb/0.1#62bb167aaa5306d1ac757bb817797f9e"
        pkgb = libb["packages"][0][0]
        assert pkgb["info"]["compatibility_delta"] == {"settings": [["compiler.cppstd", "17"]]}
        assert pkgb["build_args"] == "--requires=libb/0.1 --build=compatible:libb/0.1"

        # Now lets make sure that build-order-merge works too
        c.run(f"graph build-order --requires=libb/0.1 {settings} -s compiler.version=12 "
              "--order-by=recipe --build=compatible --format=json",
              redirect_stdout="build_order2.json")
        c.run(f"graph build-order-merge --file=build_order.json --file=build_order2.json -f=json",
              redirect_stdout="build_order_merged.json")
        bo = json.loads(c.load("build_order_merged.json"))
        liba = bo["order"][0][0]
        assert liba["ref"] == "liba/0.1#c1459d256a9c2d3c49d149fd7c43310c"
        for pkg_index in (0, 1):
            pkga = liba["packages"][0][pkg_index]
            assert pkga["info"]["compatibility_delta"] == {"settings": [["compiler.cppstd", "14"]]}
            assert pkga["build_args"] == "--requires=liba/0.1 --build=compatible:liba/0.1"
