import textwrap
import unittest
from parameterized import parameterized

from conans.test.utils.tools import TestClient, GenConanfile

from conans.tools import normalized_cppstd


class CompatibleCppstdIDsTest(unittest.TestCase):

    def test_defaults(self):
        """ Test default behaviour
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=14
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package '50770693c0b21b53b3cc2d1544b1c7ab89c66862'"
                      " created", client.out)

        # Forward compatible by default
        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd=17")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: 14!", client.out)
        self.assertIn("pkg/0.1@user/stable:50770693c0b21b53b3cc2d1544b1c7ab89c66862", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

        # GNU extension compatible by default
        client.run("install . -pr=myprofile -s=compiler.cppstd=gnu17")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: 14!", client.out)
        self.assertIn("pkg/0.1@user/stable:50770693c0b21b53b3cc2d1544b1c7ab89c66862", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Backwards incompatible by default
        client.run("install . -pr=myprofile -s=compiler.cppstd=11", assert_error=True)
        self.assertIn("Missing prebuilt package for 'pkg/0.1@user/stable'", client.out)

    def test_compatible_none(self):
        """ None value is correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
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
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package '763b775a30a2c7b64c33dd4364ab6fccd7266f9e'"
                      " created", client.out)

        # Still works
        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd=17")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: None!", client.out)
        self.assertIn("pkg/0.1@user/stable:763b775a30a2c7b64c33dd4364ab6fccd7266f9e", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_forward_compatible_versions(self, cppstd):
        """ Forward compatible versions are correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'feeffcef577f146f356dfbe26df0e582f154e094'"
                      " created", client.out)

        # Forward compatible
        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: 11!", client.out)
        self.assertIn("pkg/0.1@user/stable:feeffcef577f146f356dfbe26df0e582f154e094", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_forward_incompatible_versions(self, cppstd):
        """ Forward incompatible versions are correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17, forward=False)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=98
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'e272878107501abbf089754432ee1a7f97046e9f'"
                      " created", client.out)

        # Backward incompatible
        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self.assertIn("Missing prebuilt package for 'pkg/0.1@user/stable'", client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_backward_compatible_versions(self, cppstd):
        """ Backward compatible versions are correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17, backward=True)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=gnu17
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package '300bea41e283e935af20532076ca08efa54a75b3'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: gnu17!", client.out)
        self.assertIn("pkg/0.1@user/stable:300bea41e283e935af20532076ca08efa54a75b3", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

    @parameterized.expand(["11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_forward_incompatible_versions(self, cppstd):
        """ Forward incompatible versions are correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17, forward=False)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=20
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package '5be5f0dcb97ab72e0a45c48d3e954b4364e19a55'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self.assertIn("Missing prebuilt package for 'pkg/0.1@user/stable'", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

    @parameterized.expand(["11", "14", "17"])
    def test_gnu_compatible_versions(self, cppstd):
        """ Gnu extension compatibility is correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'feeffcef577f146f356dfbe26df0e582f154e094'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: 11!", client.out)
        self.assertIn("pkg/0.1@user/stable:feeffcef577f146f356dfbe26df0e582f154e094", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

    @parameterized.expand(["gnu11", "gnu14", "gnu17"])
    def test_gnu_compatible_versions_with_gnu(self, cppstd):
        """ Gnu extension compatibility is correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=gnu11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'c8fa89d95ea240695a5c77dcf084119108ebdb95'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: gnu11!", client.out)
        self.assertIn("pkg/0.1@user/stable:c8fa89d95ea240695a5c77dcf084119108ebdb95", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

    @parameterized.expand(["11", "14", "17"])
    def test_gnu_incompatible_versions(self, cppstd):
        """ Gnu extension incompatibility is correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=gnu11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'c8fa89d95ea240695a5c77dcf084119108ebdb95'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self.assertIn("Missing prebuilt package for 'pkg/0.1@user/stable'", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

    @parameterized.expand(["gnu11", "gnu14", "gnu17"])
    def test_gnu_incompatible_versions_with_gnu(self, cppstd):
        """ Gnu extension incompatibility is correctly handled
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import compatible_cppstd

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_cppstd(self, min=11, max=17, gnu_extensions_compatible=False)
                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: {}!"
                                     .format(self.settings.compiler.cppstd))
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'feeffcef577f146f356dfbe26df0e582f154e094'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self.assertIn("Missing prebuilt package for 'pkg/0.1@user/stable'", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

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
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'feeffcef577f146f356dfbe26df0e582f154e094'"
                      " created", client.out)

        # Forward compatible
        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: 11!", client.out)
        self.assertIn("pkg/0.1@user/stable:feeffcef577f146f356dfbe26df0e582f154e094", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

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
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'feeffcef577f146f356dfbe26df0e582f154e094'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd))
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Cppstd version: 11!", client.out)
        self.assertIn("pkg/0.1@user/stable:feeffcef577f146f356dfbe26df0e582f154e094", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

        # Don't add the same configuration into compatible packages
        self.assertNotIn("equal to the default package ID", client.out)

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
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=11
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'feeffcef577f146f356dfbe26df0e582f154e094'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s=compiler.cppstd={}".format(cppstd), assert_error=True)
        self.assertIn("Missing prebuilt package for 'pkg/0.1@user/stable'", client.out)

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
        old_profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=98
            compiler.libcxx=libstdc++
            """)
        old_hash = "e272878107501abbf089754432ee1a7f97046e9f"
        new_profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=8
            compiler.cppstd=17
            compiler.libcxx=libstdc++
            """)
        new_hash = "09747d520eddddbd02bdacc43dc5e2f210cc0568"
        client.save({"conanfile.py": conanfile,
                     "old_profile": old_profile,
                     "new_profile": new_profile})
        client.run("create . pkg/0.1@user/stable -pr=old_profile")
        self.assertIn("pkg/0.1@user/stable: Package '{}' created".format(old_hash), client.out)
        client.run("create . pkg/0.1@user/stable -pr=new_profile")
        self.assertIn("pkg/0.1@user/stable: Package '{}' created".format(new_hash), client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=old_profile -s=compiler.cppstd={}".format(cppstd))

        if normalized_cppstd(cppstd) < "2017":
            version = "98"
            current_hash = old_hash
        else:
            version = "17"
            current_hash = new_hash

        self.assertIn(
            "pkg/0.1@user/stable: PackageInfo!: Cppstd version: {}!".format(version), client.out)
        self.assertIn("pkg/0.1@user/stable:{}".format(current_hash), client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
