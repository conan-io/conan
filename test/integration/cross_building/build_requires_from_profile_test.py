import unittest
import textwrap

from conan.test.utils.tools import TestClient, GenConanfile


class BuildRequiresFromProfileTest(unittest.TestCase):
    profile_host = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
         compiler=msvc
        compiler.version=192
        compiler.runtime=dynamic

        [tool_requires]
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

        [tool_requires]
        br3/version
    """)

    library_conanfile = textwrap.dedent("""
        from conan import ConanFile

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
        t.run("export br1.py --name=br1 --version=version")
        t.run("export br2.py --name=br2 --version=version")
        t.run("export br3.py --name=br3 --version=version")
        t.run("create library.py --profile:host=profile_host --profile:build=profile_build "
              "--build='*'")


class BuildRequiresContextHostFromProfileTest(unittest.TestCase):
    toolchain = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):
            name = "mytoolchain"
            version = "1.0"
            settings = "os"

            def package_info(self):
                self.output.info("PackageInfo OS=%s" % self.settings.os)
        """)
    gtest = textwrap.dedent("""
        from conan import ConanFile
        import os

        class Recipe(ConanFile):
            name = "gtest"
            version = "1.0"
            settings = "os"

            def build(self):
                self.output.info("Build OS=%s" % self.settings.os)
            def package_info(self):
                self.output.info("PackageInfo OS=%s" % self.settings.os)
        """)
    library_conanfile = textwrap.dedent("""
         from conan import ConanFile
         import os

         class Recipe(ConanFile):
             name = "library"
             version = "version"
             settings = "os"

             def build_requirements(self):
                self.test_requires("gtest/1.0")

             def build(self):
                self.output.info("Build OS=%s" % self.settings.os)
         """)
    profile_host = textwrap.dedent("""
        [settings]
        os = Linux
        [tool_requires]
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
        t.run("create mytoolchain.py -pr:h=profile_host -pr:b=profile_build --build-require")

        t.run("create gtest.py -pr=profile_host -pr:b=profile_build")
        self.assertIn("mytoolchain/1.0: PackageInfo OS=Windows", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)

        t.run("create gtest.py -pr=profile_host -pr:b=profile_build --build=*")
        self.assertIn("mytoolchain/1.0: PackageInfo OS=Windows", t.out)
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)

        t.run("create library.py -pr:h=profile_host -pr:b=profile_build")
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)
        self.assertIn("library/version: Build OS=Linux", t.out)
        self.assertIn("mytoolchain/1.0: PackageInfo OS=Windows", t.out)

        t.run("create library.py -pr:h=profile_host -pr:b=profile_build --build=*")
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)
        self.assertIn("library/version: Build OS=Linux", t.out)
        self.assertIn("mytoolchain/1.0: PackageInfo OS=Windows", t.out)


class BuildRequiresBothContextsTest(unittest.TestCase):
    toolchain_creator = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):
            name = "creator"
            version = "1.0"
            settings = "os"

            def package_info(self):
                self.output.info("PackageInfo OS=%s" % self.settings.os)
        """)
    toolchain = textwrap.dedent("""
        from conan import ConanFile
        import os

        class Recipe(ConanFile):
            name = "mytoolchain"
            version = "1.0"
            settings = "os"
            def build(self):
                self.output.info("Build OS=%s" % self.settings.os)

            def package_info(self):
                self.output.info("PackageInfo OS=%s" % self.settings.os)
        """)
    gtest = textwrap.dedent("""
        from conan import ConanFile
        import os

        class Recipe(ConanFile):
            name = "gtest"
            version = "1.0"
            settings = "os"

            def build(self):
                self.output.info("Build OS=%s" % self.settings.os)
            def package_info(self):
                self.output.info("PackageInfo OS=%s" % self.settings.os)
        """)
    library_conanfile = textwrap.dedent("""
         from conan import ConanFile
         import os

         class Recipe(ConanFile):
             name = "library"
             version = "version"
             settings = "os"

             def build_requirements(self):
                self.test_requires("gtest/1.0")

             def build(self):
                self.output.info("Build OS=%s" % self.settings.os)
         """)
    profile_host = textwrap.dedent("""
        [settings]
        os = Linux
        [tool_requires]
        mytoolchain/1.0
        """)
    profile_build = textwrap.dedent("""
        [settings]
        os = Windows
        [tool_requires]
        mytoolchain*:creator/1.0
        """)

    def test_build_requires_both_contexts(self):
        t = TestClient()
        t.save({'profile_host': self.profile_host,
                'profile_build': self.profile_build,
                'library.py': self.library_conanfile,
                'creator.py': self.toolchain_creator,
                'mytoolchain.py': self.toolchain,
                "gtest.py": self.gtest})
        t.run("create creator.py -pr=profile_build")
        t.run("create mytoolchain.py -pr:h=profile_host -pr:b=profile_build --build-require")
        self.assertIn("creator/1.0: PackageInfo OS=Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)

        # new way, the toolchain can now run in Windows, but gtest in Linux
        t.run("create gtest.py --profile=profile_host --profile:build=profile_build")
        self.assertNotIn("creator/1.0: PackageInfo", t.out)  # Creator is skipped now, not needed
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)

        t.run("create gtest.py --profile=profile_host --profile:build=profile_build --build=*")
        self.assertIn("creator/1.0: PackageInfo OS=Windows", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)

        # Declaring the build_requires in the recipe works, it is just the profile that is
        # not transitive
        toolchain = textwrap.dedent("""
            from conan import ConanFile
            import os

            class Recipe(ConanFile):
                name = "mytoolchain"
                version = "1.0"
                settings = "os"
                build_requires = "creator/1.0"
                def build(self):
                    self.output.info("Build OS=%s" % self.settings.os)

                def package_info(self):
                    self.output.info("PackageInfo OS=%s" % self.settings.os)
            """)
        t.save({'mytoolchain.py': toolchain})
        t.run("create mytoolchain.py --profile:host=profile_build -pr:b=profile_build")
        self.assertIn("creator/1.0: PackageInfo OS=Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)

        t.run("create gtest.py --profile=profile_host --profile:build=profile_build --build=*")
        self.assertIn("creator/1.0: PackageInfo OS=Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)

        t.run("create library.py -pr:h=profile_host --profile:build=profile_build --build=*")
        self.assertIn("creator/1.0: PackageInfo OS=Windows", t.out)
        self.assertIn("mytoolchain/1.0: Build OS=Windows", t.out)
        self.assertIn("gtest/1.0: Build OS=Linux", t.out)
        self.assertIn("gtest/1.0: PackageInfo OS=Linux", t.out)
        self.assertIn("library/version: Build OS=Linux", t.out)
