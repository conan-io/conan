import unittest
import textwrap
from conans.test.utils.tools import TestClient, GenConanfile


class BuildRequiresFromProfile(unittest.TestCase):
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
        t.run("create library.py --profile:host=profile_host --profile:build=profile_build --build *")
        self.assertNotIn("br1/version: Applying build-requirement: br2/version", t.out)
        self.assertIn("br1/version: Applying build-requirement: br3/version", t.out)
        self.assertIn("library/version: Applying build-requirement: br2/version", t.out)
        self.assertIn("library/version: Applying build-requirement: br1/version", t.out)


class BuildRequiresContextHostFromProfile(unittest.TestCase):
    toolchain = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "mytoolchain"
            version = "1.0"

            def package_info(self):
                self.env_info.MYTOOLCHAIN_VAR = "MYTOOLCHAIN_VALUE"
        """)
    gtest = textwrap.dedent("""
        from conans import ConanFile
        import os

        class Recipe(ConanFile):
            name = "gtest"
            version = "1.0"

            def build(self):
                self.output.info("Building with: %s" % os.getenv("MYTOOLCHAIN_VAR"))
        """)
    library_conanfile = textwrap.dedent("""
         from conans import ConanFile
         import os

         class Recipe(ConanFile):
             name = "library"
             version = "version"

             def build_requirements(self):
                self.build_requires("gtest/1.0", force_host_context=True)

             def build(self):
                self.output.info("Building with: %s" % os.getenv("MYTOOLCHAIN_VAR"))
         """)
    profile_host = textwrap.dedent("""
        [build_requires]
        mytoolchain/1.0
        """)

    def test_br_from_profile_host_and_profile_build(self):
        t = TestClient()
        t.save({'profile_host': self.profile_host,
                'profile_build': "",
                'library.py': self.library_conanfile,
                'mytoolchain.py': self.toolchain,
                "gtest.py": self.gtest})
        t.run("create mytoolchain.py")
        t.run("create gtest.py --profile=profile_host")
        self.assertIn("gtest/1.0: Building with: MYTOOLCHAIN_VALUE", t.out)

        t.run("create library.py --profile:host=profile_host --profile:build=profile_build --build")
        self.assertIn("gtest/1.0: Building with: MYTOOLCHAIN_VALUE", t.out)
        self.assertIn("library/version: Building with: MYTOOLCHAIN_VALUE", t.out)
