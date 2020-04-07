import textwrap
import unittest
from parameterized import parameterized

from conans.test.utils.tools import TestClient, GenConanfile

from conans.tools import normalized_cppstd


class CompatibleCppstdTest(unittest.TestCase):
    CONANFILE = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import compatible_cppstd

        class Pkg(ConanFile):
            settings = "os", "compiler"
            def package_id(self):
                {!}
            def package_info(self):
                self.output.info("PackageInfo!: Cppstd version: {}!"
                                    .format(self.settings.compiler.cppstd))
        """)
    PROFILE = textwrap.dedent("""
        [settings]
        os = Linux
        compiler=gcc
        compiler.version=8
        compiler.cppstd={!}
        compiler.libcxx=libstdc++
        """)

    def _assert_created(self, hash, out):
        self.assertIn("pkg/0.1@user/stable: Package '{}' created".format(hash), out)

    def _assert_compatible(self, cppstd, hash, out):
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: {}!".format(cppstd), out)
        self.assertIn("pkg/0.1@user/stable:{}".format(hash), out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", out)

    def _assert_incompatible(self, out):
        self.assertIn("Missing prebuilt package for 'pkg/0.1@user/stable'", out)

    def _assert_no_same_config(self, out):
        """ Don't add the same configuration into compatible packages
        """
        self.assertNotIn("equal to the default package ID", out)

    def test_defaults(self):
        """ Test default behaviour
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "14")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "50770693c0b21b53b3cc2d1544b1c7ab89c66862"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        # Forward compatible by default
        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd=17")
        self._assert_compatible("14", package_hash, client.out)

        self._assert_no_same_config(client.out)

        # GNU extension compatible by default
        client.run("install . -pr=myprofile -s=compiler.cppstd=gnu17")
        self._assert_compatible("14", package_hash, client.out)

        # Backwards incompatible by default
        client.run("install . -pr=myprofile -s=compiler.cppstd=11", assert_error=True)
        self._assert_incompatible(client.out)

    def test_compatible_none(self):
        """ None value is correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self)")
        profile = textwrap.dedent("""
            [settings]
            os = Windows
            compiler=Visual Studio
            compiler.version=15
            compiler.cppstd=14
            compiler.runtime=MD
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "763b775a30a2c7b64c33dd4364ab6fccd7266f9e"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd=17")
        self._assert_compatible("None", package_hash, client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_forward_compatible_versions(self, cppstd):
        """ Forward compatible versions are correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "feeffcef577f146f356dfbe26df0e582f154e094"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self._assert_compatible("11", package_hash, client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_forward_incompatible_versions(self, cppstd):
        """ Forward incompatible versions are correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17, forward=False)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "98")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "e272878107501abbf089754432ee1a7f97046e9f"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self._assert_incompatible(client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_backward_compatible_versions(self, cppstd):
        """ Backward compatible versions are correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17, backward=True)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "gnu17")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "300bea41e283e935af20532076ca08efa54a75b3"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self._assert_compatible("gnu17", package_hash, client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_forward_incompatible_versions(self, cppstd):
        """ Forward incompatible versions are correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17, forward=False)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "20")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "5be5f0dcb97ab72e0a45c48d3e954b4364e19a55"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self._assert_incompatible(client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["11", "14", "17"])
    def test_gnu_compatible_versions(self, cppstd):
        """ Gnu extension compatibility is correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "feeffcef577f146f356dfbe26df0e582f154e094"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self._assert_compatible("11", package_hash, client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["gnu11", "gnu14", "gnu17"])
    def test_gnu_compatible_versions_with_gnu(self, cppstd):
        """ Gnu extension compatibility is correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "gnu11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "c8fa89d95ea240695a5c77dcf084119108ebdb95"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self._assert_compatible("gnu11", package_hash, client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["11", "14", "17"])
    def test_gnu_incompatible_versions(self, cppstd):
        """ Gnu extension incompatibility is correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "gnu11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "c8fa89d95ea240695a5c77dcf084119108ebdb95"

        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self._assert_incompatible(client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["gnu11", "gnu14", "gnu17"])
    def test_gnu_incompatible_versions_with_gnu(self, cppstd):
        """ Gnu extension incompatibility is correctly handled
        """
        client = TestClient()

        conanfile = CompatibleCppstdTest.CONANFILE.replace(
            "{!}", "compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)")
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "feeffcef577f146f356dfbe26df0e582f154e094"

        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self._assert_incompatible(client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_concatenate_compatible_versions(self, cppstd):
        """ Concatenated ranges should behave correctly
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=14)
                    compatible_cppstd(self, min=14, max=17)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "feeffcef577f146f356dfbe26df0e582f154e094"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self._assert_compatible("11", package_hash, client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_overlap_compatible_versions(self, cppstd):
        """ Overlapped ranges should behave correctly
        """
        client = TestClient()

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=98, max=17)
                    compatible_cppstd(self, min=11, max=20)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "feeffcef577f146f356dfbe26df0e582f154e094"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self._assert_compatible("11", package_hash, client.out)
        self._assert_no_same_config(client.out)

    @parameterized.expand(["gnu11", "14", "gnu14", "17", "gnu17"])
    def test_no_overlap_compatible_versions(self, cppstd):
        """ Ranges without overlap should behave correctly
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=98, max=98)
                    compatible_cppstd(self, min=20, max=20)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "11")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        package_hash = "feeffcef577f146f356dfbe26df0e582f154e094"

        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self._assert_created(package_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self._assert_incompatible(client.out)

    @parameterized.expand(["98", "gnu98", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20"])
    def test_split_compatible_versions(self, cppstd):
        """ Splitted ranges should behave correctly
        """
        client = TestClient()

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd, deduced_cppstd, normalized_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    if normalized_cppstd(deduced_cppstd(self)) < "2017":
                        compatible_cppstd(self, max=14)
                    else:
                        compatible_cppstd(self, min=17)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        old_profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "98")
        old_hash = "e272878107501abbf089754432ee1a7f97046e9f"
        new_profile = CompatibleCppstdTest.PROFILE.replace(
            "{!}", "17")
        new_hash = "09747d520eddddbd02bdacc43dc5e2f210cc0568"
        client.save({"conanfile.py": conanfile,
                     "old_profile": old_profile,
                     "new_profile": new_profile})

        client.run("create . pkg/0.1@user/stable -pr=old_profile")
        self._assert_created(old_hash, client.out)
        client.run("create . pkg/0.1@user/stable -pr=new_profile")
        self._assert_created(new_hash, client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=old_profile -s=compiler.cppstd={}".format(cppstd))

        if normalized_cppstd(cppstd) < "2017":
            version = "98"
            current_hash = old_hash
        else:
            version = "17"
            current_hash = new_hash

        self._assert_compatible(version, current_hash, client.out)
