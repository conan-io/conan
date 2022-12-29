import unittest
import textwrap
from conans.test.utils.tools import TestClient, GenConanfile


class BuildRequiresFromProfileTest(unittest.TestCase):
    profile_host = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=16

        [build_requires]
        br2/version
    """)

    profile_build = textwrap.dedent("""
        [settings]
        os=Macos
        arch=x86_64
        compiler=apple-clang
        compiler.version=11.0
        compiler.libcxx=libc++
        build_type=Release

        [build_requires]
        br3/version
    """)

    library_conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "library"
            version = "version"

            build_requires = "br1/version"
    """)

    def test_br_from_profile_host_and_profile_build(self):
        t = TestClient()
        t.save({'profile_host': self.profile_host,
                'profile_build': self.profile_build,
                'library.py': self.library_conanfile,
                'br1.py': GenConanfile(),
                'br2.py': GenConanfile(),
                'br3.py': GenConanfile()})
        t.run("export br1.py br1/version@")
        t.run("export br2.py br2/version@")
        t.run("export br3.py br3/version@")
        t.run("create library.py --profile:host=profile_host --profile:build=profile_build --build")
        self.assertNotIn("br1/version: Applying build-requirement: br2/version", t.out)
        self.assertIn("br1/version: Applying build-requirement: br3/version", t.out)
        self.assertIn("library/version: Applying build-requirement: br2/version", t.out)
        self.assertIn("library/version: Applying build-requirement: br1/version", t.out)


class BuildRequiresContextHostFromProfileTest(unittest.TestCase):
    toolchain = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "mytoolchain"
            version = "1.0"
            settings = "os"

            def package_info(self):
                self.env_info.MYTOOLCHAIN_VAR = "MYTOOLCHAIN_VALUE-" + str(self.settings.os)
        """)
    gtest = textwrap.dedent("""
        from conans import ConanFile
        import os

        class Recipe(ConanFile):
            name = "gtest"
            version = "1.0"
            settings = "os"

            def build(self):
                self.output.info("Building with: %s" % os.getenv("MYTOOLCHAIN_VAR"))
                self.output.info("Build OS=%s" % self.settings.os)
            def package_info(self):
                self.output.info("PackageInfo OS=%s" % self.settings.os)
        """)
    library_conanfile = textwrap.dedent("""
         from conans import ConanFile
         import os

         class Recipe(ConanFile):
             name = "library"
             version = "version"
             settings = "os"

             def build_requirements(self):
                self.build_requires("gtest/1.0", force_host_context=True)

             def build(self):
                self.output.info("Building with: %s" % os.getenv("MYTOOLCHAIN_VAR"))
                self.output.info("Build OS=%s" % self.settings.os)
         """)
    profile_host = textwrap.dedent("""
        [settings]
        os = Linux
        [build_requires]
        mytoolchain/1.0
        """)
    profile_build = textwrap.dedent("""
        [settings]
        os = Windows
        """)

    def test_br_from_profile_host_and_profile_build(self):
        t = TestClient()
        t.save({'profile_host': self.profile_host,
                'profile_build': self.profile_build,
                'library.py': self.library_conanfile,
                'mytoolchain.py': self.toolchain,
                "gtest.py": self.gtest})
        t.run("create mytoolchain.py --profile=profile_build")
        t.run("create mytoolchain.py --profile=profile_host")

        # old way, the toolchain will have the same profile (profile_host=Linux) only
        t.run("create gtest.py --profile=profile_host")
        self.assertIn("gtest/1.0: Building with: MYTOOLCHAIN_VALUE-Linux", t.out)
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)

        # new way, the toolchain can now run in Windows, but gtest in Linux
        t.run("create gtest.py --profile=profile_host --profile:build=profile_build")
        self.assertIn("gtest/1.0: Building with: MYTOOLCHAIN_VALUE-Windows", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)

        t.run("create gtest.py --profile=profile_host --profile:build=profile_build --build")
        self.assertIn("gtest/1.0: Building with: MYTOOLCHAIN_VALUE-Windows", t.out)
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)

        t.run("create library.py --profile:host=profile_host --profile:build=profile_build")
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)
        self.assertIn("library/version: Build OS=Linux", t.out)
        self.assertIn("library/version: Building with: MYTOOLCHAIN_VALUE-Windows", t.out)

        t.run("create library.py --profile:host=profile_host --profile:build=profile_build --build")
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)
        self.assertIn("library/version: Build OS=Linux", t.out)
        self.assertIn("library/version: Building with: MYTOOLCHAIN_VALUE-Windows", t.out)


class BuildRequiresBothContextsTest(unittest.TestCase):
    toolchain_creator = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "creator"
            version = "1.0"
            settings = "os"

            def package_info(self):
                self.env_info.MYCREATOR_VAR = "MYCREATOR_VALUE-" + str(self.settings.os)
        """)
    toolchain = textwrap.dedent("""
        from conans import ConanFile
        import os

        class Recipe(ConanFile):
            name = "mytoolchain"
            version = "1.0"
            settings = "os"
            def build(self):
                self.output.info("Building with: %s" % os.environ["MYCREATOR_VAR"])
                self.output.info("Build OS=%s" % self.settings.os)

            def package_info(self):
                self.env_info.MYTOOLCHAIN_VAR = "MYTOOLCHAIN_VALUE-" + str(self.settings.os)
        """)
    gtest = textwrap.dedent("""
        from conans import ConanFile
        import os

        class Recipe(ConanFile):
            name = "gtest"
            version = "1.0"
            settings = "os"

            def build(self):
                self.output.info("Building with: %s" % os.environ["MYTOOLCHAIN_VAR"])
                self.output.info("Build OS=%s" % self.settings.os)
            def package_info(self):
                self.output.info("PackageInfo OS=%s" % self.settings.os)
        """)
    library_conanfile = textwrap.dedent("""
         from conans import ConanFile
         import os

         class Recipe(ConanFile):
             name = "library"
             version = "version"
             settings = "os"

             def build_requirements(self):
                self.build_requires("gtest/1.0", force_host_context=True)

             def build(self):
                self.output.info("Building with: %s" % os.environ["MYTOOLCHAIN_VAR"])
                self.output.info("Build OS=%s" % self.settings.os)
         """)
    profile_host = textwrap.dedent("""
        [settings]
        os = Linux
        [build_requires]
        mytoolchain/1.0
        """)
    profile_build = textwrap.dedent("""
        [settings]
        os = Windows
        [build_requires]
        creator/1.0
        """)

    def test_build_requires_both_contexts(self):
        t = TestClient()
        t.save({'profile_host': self.profile_host,
                'profile_build': self.profile_build,
                'library.py': self.library_conanfile,
                'creator.py': self.toolchain_creator,
                'mytoolchain.py': self.toolchain,
                "gtest.py": self.gtest})
        t.run("create creator.py --profile=profile_build")
        t.run("create mytoolchain.py --profile=profile_build")
        self.assertIn("mytoolchain/1.0: Building with: MYCREATOR_VALUE-Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)

        # new way, the toolchain can now run in Windows, but gtest in Linux
        t.run("create gtest.py --profile=profile_host --profile:build=profile_build")
        self.assertIn("gtest/1.0: Building with: MYTOOLCHAIN_VALUE-Windows", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)

        # FIXME: This isn't right, it should be CREATOR-Windows, but build_requires
        # FIXME: from profiles are not transitive to build_requires in profiles
        t.run("create gtest.py --profile=profile_host --profile:build=profile_build --build",
              assert_error=True)
        self.assertIn("ERROR: mytoolchain/1.0: Error in build() method, line 10", t.out)
        self.assertIn("KeyError: 'MYCREATOR_VAR'", t.out)

        # Declaring the build_requires in the recipe works, it is just the profile that is
        # not transitive
        toolchain = textwrap.dedent("""
            from conans import ConanFile
            import os

            class Recipe(ConanFile):
                name = "mytoolchain"
                version = "1.0"
                settings = "os"
                build_requires = "creator/1.0"
                def build(self):
                    self.output.info("Building with: %s" % os.environ["MYCREATOR_VAR"])
                    self.output.info("Build OS=%s" % self.settings.os)

                def package_info(self):
                    self.env_info.MYTOOLCHAIN_VAR = "MYTOOLCHAIN_VALUE-" + str(self.settings.os)
            """)
        t.save({'mytoolchain.py': toolchain})
        t.run("create mytoolchain.py --profile=profile_build")
        self.assertIn("mytoolchain/1.0: Building with: MYCREATOR_VALUE-Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)

        t.run("create gtest.py --profile=profile_host --profile:build=profile_build --build")
        self.assertIn("mytoolchain/1.0: Building with: MYCREATOR_VALUE-Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)
        self.assertIn("gtest/1.0: Building with: MYTOOLCHAIN_VALUE-Windows", t.out)
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)

        t.run("create library.py --profile:host=profile_host --profile:build=profile_build --build")
        self.assertIn("mytoolchain/1.0: Building with: MYCREATOR_VALUE-Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)
        self.assertIn("library/version: Build OS=Linux", t.out)
        self.assertIn("library/version: Building with: MYTOOLCHAIN_VALUE-Windows", t.out)
