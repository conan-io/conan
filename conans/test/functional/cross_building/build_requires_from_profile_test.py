import unittest
import textwrap
from conans.test.utils.tools import TestClient, TestServer, GenConanfile


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
    """)

    library_conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "library"
            version = "version"

            build_requires = "br1/version"
    """)

    def test_br_from_profile(self):
        t = TestClient()
        t.save({'profile_host': self.profile_host,
                'profile_build': self.profile_build,
                'library.py': self.library_conanfile,
                'br1.py': GenConanfile(),
                'br2.py': GenConanfile()})
        t.run("export br1.py br1/version@")
        t.run("export br2.py br2/version@")
        t.run("create library.py --profile:host=profile_host --profile:build=profile_build --build *")
        self.assertNotIn("br1/version: Applying build-requirement: br2/version", t.out)
