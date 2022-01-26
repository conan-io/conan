import textwrap
import time
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class CompatibleIDsTest(unittest.TestCase):

    def test_compatible_setting(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        for version in ("4.8", "4.7", "4.6"):
                            compatible_pkg = self.info.clone()
                            compatible_pkg.settings.compiler.version = version
                            self.compatible_packages.append(compatible_pkg)
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
               def package_id(self):
                   if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                       for version in ("4.8", "4.7", "4.6"):
                           compatible_pkg = self.info.clone()
                           compatible_pkg.settings.compiler.version = version
                           self.compatible_packages.append(compatible_pkg)
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
        self.assertIn("pkg/0.1@user/stable: Exported revision: aa6c81a7746c85101bc5c8d9f870660b",
                      client.out)

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        # No fallback
        client.run("install . -pr=myprofile --build=missing")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.9!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable":
                                     ("c6715d73365c2dd62f68836b2dee8359a312ff12", "Build")})

    def test_compatible_setting_no_user_channel(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        for version in ("4.8", "4.7", "4.6"):
                            compatible_pkg = self.info.clone()
                            compatible_pkg.settings.compiler.version = version
                            self.compatible_packages.append(compatible_pkg)
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
                def package_id(self):
                    for optimized in range(int(self.options.optimized), 0, -1):
                        compatible_pkg = self.info.clone()
                        compatible_pkg.options.optimized = optimized
                        self.compatible_packages.append(compatible_pkg)
                def package_info(self):
                    self.output.info("PackageInfo!: Option optimized %s!"
                                     % self.options.optimized)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable")
        package_id = client.created_package_id("pkg/0.1@user/stable")
        self.assertIn(f"pkg/0.1@user/stable: Package '{package_id}' created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("install . -o pkg:optimized=2")
        # Information messages
        missing_id = "508da41e46d27c4c4996d7b31df7942c7bba1e27"
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Option optimized 1!", client.out)
        self.assertIn("pkg/0.1@user/stable: Compatible package ID "
                      f"{missing_id} equal to the default package ID",
                      client.out)
        self.assertIn("pkg/0.1@user/stable: Main binary package "
                      f"'{missing_id}' missing. Using compatible package"
                      f" '{package_id}'", client.out)
        # checking the resulting dependencies
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        client.run("install . -o pkg:optimized=3")
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def test_visual_package_compatible_with_intel(self):
        client = TestClient()
        ref = RecipeReference.loads("bye/0.1@us/ch")
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Conan(ConanFile):
            settings = "compiler"

            def package_id(self):
                if self.settings.compiler == "intel":
                    p = self.info.clone()
                    p.base_compatible()
                    self.compatible_packages.append(p)
            """)
        visual_profile = textwrap.dedent("""
            [settings]
            compiler = Visual Studio
            compiler.version = 8
            compiler.runtime = MD
            """)
        intel_profile = textwrap.dedent("""
            [settings]
            compiler = intel
            compiler.version = 16
            compiler.update = 311
            compiler.base = Visual Studio
            compiler.base.version = 8
            compiler.base.runtime = MD
            """)
        client.save({"conanfile.py": conanfile,
                     "intel_profile": intel_profile,
                     "visual_profile": visual_profile})
        client.run("create . --name=bye --version=0.1 --user=us --channel=ch "
                   "--profile visual_profile")
        package_id = client.created_package_id("bye/0.1@us/ch")
        client.run("install --reference=%s -pr intel_profile" % repr(ref))
        missing_id = "c1b60feb368929efd9e60fd47dbfa45969742332"
        self.assertIn(f"bye/0.1@us/ch: Main binary package '{missing_id}'"
                      " missing. Using compatible package "
                      f"'{package_id}'", client.out)
        client.assert_listed_binary({"bye/0.1@us/ch": (package_id, "Cache")})

    def test_wrong_base_compatible(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Conan(ConanFile):
            settings = "compiler"

            def package_id(self):
                p = self.info.clone()
                p.base_compatible()
                self.compatible_packages.append(p)
            """)
        visual_profile = textwrap.dedent("""
            [settings]
            compiler = Visual Studio
            compiler.version = 8
            compiler.runtime = MD
            """)
        client.save({"conanfile.py": conanfile,
                     "visual_profile": visual_profile})
        client.run("create . --name=bye --version=0.1 --user=us --channel=ch "
                   "--profile visual_profile", assert_error=True)
        self.assertIn("The compiler 'Visual Studio' has no 'base' sub-setting", client.out)

    def test_intel_package_compatible_with_base(self):
        client = TestClient()
        ref = RecipeReference.loads("bye/0.1@us/ch")
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Conan(ConanFile):
            settings = "compiler"

            def package_id(self):
               if self.settings.compiler == "Visual Studio":
                   compatible_pkg = self.info.clone()
                   compatible_pkg.parent_compatible(compiler="intel", version=16)
                   self.compatible_packages.append(compatible_pkg)

            """)
        visual_profile = textwrap.dedent("""
            [settings]
            compiler = Visual Studio
            compiler.version = 8
            compiler.runtime = MD
            """)
        intel_profile = textwrap.dedent("""
            [settings]
            compiler = intel
            compiler.version = 16
            compiler.base = Visual Studio
            compiler.base.version = 8
            compiler.base.runtime = MD
            """)
        client.save({"conanfile.py": conanfile,
                     "intel_profile": intel_profile,
                     "visual_profile": visual_profile})
        client.run("create . --name=bye --version=0.1 --user=us --channel=ch "
                   "--profile intel_profile")
        package_id = client.created_package_id("bye/0.1@us/ch")
        client.run("install --reference=%s -pr visual_profile" % repr(ref))
        missing_id = "6e399d2c50620569974e4d894ee9651ee7861be9"
        self.assertIn("bye/0.1@us/ch: Main binary package "
                      f"'{missing_id}' missing. Using compatible "
                      f"package '{package_id}'",
                      client.out)
        client.assert_listed_binary({"bye/0.1@us/ch": (package_id, "Cache")})

    def test_no_valid_compiler_keyword_base(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Conan(ConanFile):
            settings = "compiler"

            def package_id(self):
               if self.settings.compiler == "Visual Studio":
                   compatible_pkg = self.info.clone()
                   compatible_pkg.parent_compatible("intel")
                   self.compatible_packages.append(compatible_pkg)

            """)
        visual_profile = textwrap.dedent("""
            [settings]
            compiler = Visual Studio
            compiler.version = 8
            compiler.runtime = MD
            """)
        client.save({"conanfile.py": conanfile,
                     "visual_profile": visual_profile})
        client.run("create . --name=bye --version=0.1 --user=us --channel=ch "
                   "--profile visual_profile", assert_error=True)
        self.assertIn("Specify 'compiler' as a keywork "
                      "argument. e.g: 'parent_compiler(compiler=\"intel\")'", client.out)

    def test_intel_package_invalid_subsetting(self):
        """If I specify an invalid subsetting of my base compiler, it won't fail, but it won't
        file the available package_id"""
        client = TestClient()
        ref = RecipeReference.loads("bye/0.1@us/ch")
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Conan(ConanFile):
                settings = "compiler"

                def package_id(self):
                   if self.settings.compiler == "Visual Studio":
                       compatible_pkg = self.info.clone()
                       compatible_pkg.parent_compatible(compiler="intel", version=16, FOO="BAR")
                       self.compatible_packages.append(compatible_pkg)
            """)
        visual_profile = textwrap.dedent("""
            [settings]
            compiler = Visual Studio
            compiler.version = 8
            compiler.runtime = MD
            """)
        intel_profile = textwrap.dedent("""
            [settings]
            compiler = intel
            compiler.version = 16
            compiler.base = Visual Studio
            compiler.base.version = 8
            compiler.base.runtime = MD
            """)
        client.save({"conanfile.py": conanfile,
                     "intel_profile": intel_profile,
                     "visual_profile": visual_profile})
        client.run("create . --name=bye --version=0.1 --user=us --channel=ch "
                   "--profile intel_profile")
        client.run("install --reference=%s -pr visual_profile" % repr(ref), assert_error=True)
        self.assertIn("Missing prebuilt package for 'bye/0.1@us/ch'", client.out)

    def test_additional_id_mode(self):
        c1 = GenConanfile().with_name("aa").with_version("1.0")
        c2 = GenConanfile().with_name("bb").with_version("1.0").with_require("aa/1.0")
        client = TestClient()
        # Recipe revision mode
        save(client.cache.new_config_path, "core.package_id:default_mode=recipe_revision_mode")
        # Create binaries with recipe revision mode for both
        client.save({"conanfile.py": c1})
        client.run("create .")

        client.save({"conanfile.py": c2})
        client.run("create .")

        # Back to semver default
        save(client.cache.new_config_path, "core.package_id:default_mode=semver_mode")
        client.run("install --reference=bb/1.0@", assert_error=True)
        self.assertIn("Missing prebuilt package for 'bb/1.0'", client.out)

        # What if client modifies the packages declaring a compatible_package with the recipe mode
        # Recipe revision mode
        save(client.cache.new_config_path, "core.package_id:default_mode=recipe_revision_mode")
        tmp = """

    def package_id(self):
        p = self.info.clone()
        p.requires.recipe_revision_mode()
        self.output.warning("Alternative package ID: {}".format(p.package_id()))
        self.compatible_packages.append(p)
"""
        c1 = str(c1) + tmp
        c2 = str(c2) + tmp
        # Create the packages, now with the recipe mode declared as compatible package
        time.sleep(1)  # new timestamp
        client.save({"conanfile.py": c1})
        client.run("create .")

        client.save({"conanfile.py": c2})
        client.run("create .")
        package_id = "e0acd34bb765800a963d2a0ba7d9aba33823be74"
        self.assertIn(f"Package '{package_id}' created", client.out)

        # Back to semver mode
        save(client.cache.new_config_path, "core.package_id:default_mode=semver_mode")
        client.run("install --reference=bb/1.0@ --update")
        self.assertIn(f"Using compatible package '{package_id}'", client.out)

    def test_package_id_consumers(self):
        # If we fallback to a different binary upstream and we are using a "package_revision_mode"
        # the current package should have a different binary package ID too.
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible = self.info.clone()
                    compatible.settings.compiler.version = "4.8"
                    self.compatible_packages.append(compatible)
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
        save(client.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
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
        consumer_id = "59a709644ae98b2ab3f16264e16351d155122697"
        client.assert_listed_binary({"consumer/0.1@user/stable": (consumer_id, "Build")})
        self.assertIn(f"consumer/0.1@user/stable: Package '{consumer_id}' created", client.out)

        # Create package with gcc 4.9
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'c6715d73365c2dd62f68836b2dee8359a312ff12'"
                      " created", client.out)

        # Consume it
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.9!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable":
                                         ("c6715d73365c2dd62f68836b2dee8359a312ff12", "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        consumer_id = "f701bd4dcfc2b6225a3e95cfbcfb3848ca7896f5"
        client.assert_listed_binary({"consumer/0.1@user/stable": (consumer_id, "Build")})
        self.assertIn(f"consumer/0.1@user/stable: Package '{consumer_id}' created", client.out)

    def test_build_missing(self):
        # https://github.com/conan-io/conan/issues/6133
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Conan(ConanFile):
                settings = "os"

                def package_id(self):
                   if self.settings.os == "Windows":
                       compatible = self.info.clone()
                       compatible.settings.os = "Linux"
                       self.compatible_packages.append(compatible)
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

                def package_id(self):
                   if self.settings.os == "Windows":
                       compatible = self.info.clone()
                       compatible.settings.os = "Linux"
                       self.compatible_packages.append(compatible)
                """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux")
        package_id = client.created_package_id("pkg/0.1@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("install . -s os=Windows")
        client.assert_listed_binary({"pkg/0.1@user/testing": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/testing: Already installed!", client.out)

    @pytest.mark.xfail(reason="lockfiles have been deactivated at the moment")
    def test_compatible_lockfile(self):
        # https://github.com/conan-io/conan/issues/9002
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                def package_id(self):
                    if self.settings.os == "Windows":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.os = "Linux"
                        self.compatible_packages.append(compatible_pkg)
                def package_info(self):
                    self.output.info("PackageInfo!: OS: %s!" % self.settings.os)
            """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable -s os=Linux")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: OS: Linux!", client.out)
        self.assertIn("pkg/0.1@user/stable: Package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("lock create conanfile.py -s os=Windows --lockfile-out=deps.lock")
        client.run("install conanfile.py --lockfile=deps.lock")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: OS: Linux!", client.out)
        self.assertIn("pkg/0.1@user/stable:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def test_compatible_diamond(self):
        # https://github.com/conan-io/conan/issues/9880
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                {}
                settings = "build_type"
                def package_id(self):
                    if self.settings.build_type == "Debug":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.build_type = "Release"
                        self.compatible_packages.append(compatible_pkg)
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
        assert "pkga/0.1: Main binary package '040ce2bd0189e377b2d15eb7246a4274d1c63317' missing" \
               in client.out
        client.assert_listed_binary({"pkga/0.1":
                                         ("e53d55fd33066c49eb97a4ede6cb50cd8036fe8b", "Cache")})


@pytest.mark.xfail(reason="The conf core.package_id:msvc_visual_incompatible is not passed yet")
def test_msvc_visual_incompatible():
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch")
    client = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
        compiler.cppstd=14
        build_type=Release
        arch=x86_64
        """)
    client.save({"conanfile.py": conanfile,
                 "profile": profile})
    client.run('create . --name=pkg --version=0.1 -s os=Windows -s compiler="Visual Studio" -s compiler.version=15 '
               '-s compiler.runtime=MD -s build_type=Release -s arch=x86_64')
    client.run("install --reference=pkg/0.1@ -pr=profile")
    assert "Using compatible package" in client.out
    new_config = "core.package_id:msvc_visual_incompatible=1"
    save(client.cache.new_config_path, new_config)
    client.run("install --reference=pkg/0.1@ -pr=profile", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in client.out
