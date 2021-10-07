import os
import textwrap
import unittest

import pytest

from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANINFO
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.env_reader import get_env
from conans.util.files import load


class PackageIDTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def test_cross_build_settings(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "arch", "compiler", "os_build", "arch_build"
        """
        client.save({"conanfile.py": conanfile})
        client.run('install . -s os=Windows -s compiler="Visual Studio" '
                   '-s compiler.version=15 -s compiler.runtime=MD '
                   '-s os_build=Windows -s arch_build=x86 -s compiler.toolset=v141')
        conaninfo = client.load("conaninfo.txt")
        self.assertNotIn("compiler.toolset=None", conaninfo)
        self.assertNotIn("os_build=None", conaninfo)
        self.assertNotIn("arch_build=None", conaninfo)

    def _export(self, name, version, package_id_text=None, requires=None,
                channel=None, default_option_value='"off"', settings=None):
        conanfile = GenConanfile().with_name(name).with_version(version)\
                                  .with_option(option_name="an_option", values=["on", "off"])\
                                  .with_default_option("an_option", default_option_value)\
                                  .with_package_id(package_id_text)
        if settings:
            for setting in settings:
                conanfile = conanfile.with_setting(setting)

        if requires:
            for require in requires:
                conanfile = conanfile.with_require(ConanFileReference.loads(require))

        self.client.save({"conanfile.py": str(conanfile)}, clean_first=True)
        self.client.run("export . %s" % (channel or "lasote/stable"))

    @property
    def conaninfo(self):
        return self.client.load(CONANINFO)

    def test_version_semver_schema(self):
        self._export("Hello", "1.2.0")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.Y.Z", [line.strip() for line in self.conaninfo.splitlines()])

        # Now change the Hello version and build it, if we install out requires should not be
        # needed the --build needed because Hello2 don't need to be rebuilt
        self._export("Hello", "1.5.0", package_id_text=None, requires=None)
        self.client.run("install Hello/1.5.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)

        if not self.client.cache.config.revisions_enabled:
            self.client.run("install .")
            self.assertIn("Hello2/2.3.8@lasote/stable:e0d17b497b58c730aac949f374cf0bdb533549ab",
                          self.client.out)
            self.assertIn("Hello2/2.Y.Z", [line.strip() for line in self.conaninfo.splitlines()])
        else:
            # As we have changed Hello2, the binary is not valid anymore so it won't find it
            # but will look for the same package_id
            self.client.run("install .", assert_error=True)
            self.assertIn("WARN: The package Hello2/2.3.8@lasote/stable:"
                          "e0d17b497b58c730aac949f374cf0bdb533549ab doesn't belong to the "
                          "installed recipe revision, removing folder",
                          self.client.out)
            self.assertIn("- Package ID: e0d17b497b58c730aac949f374cf0bdb533549ab",
                          self.client.out)

        # Try to change user and channel too, should be the same, not rebuilt needed
        self._export("Hello", "1.5.0", package_id_text=None, requires=None,
                     channel="memsharded/testing")
        self.client.run("install Hello/1.5.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.5.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)

        if not self.client.cache.config.revisions_enabled:
            self.client.run("install .")
            self.assertIn("Hello2/2.3.8@lasote/stable:e0d17b497b58c730aac949f374cf0bdb533549ab",
                          self.client.out)
            self.assertIn("Hello2/2.Y.Z", [line.strip() for line in self.conaninfo.splitlines()])
        else:
            self.client.run("install .", assert_error=True)
            self.assertIn("Hello2/2.3.8@lasote/stable:e0d17b497b58c730aac949f374cf0bdb533549ab",
                          self.client.out)

    def test_version_full_version_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change the user and channel should not be needed to rebuild
        self._export("Hello", "1.2.0", package_id_text=None, requires=None,
                     channel="memsharded/testing")
        self.client.run("install Hello/1.2.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        if not self.client.cache.config.revisions_enabled:
            self.client.run("install .")
            self.assertIn("Hello2/2.3.8@lasote/stable:3ec60bb399a8bcb937b7af196f6685ba878aab02",
                          self.client.out)
        else:
            # As we have changed Hello2, the binary is not valid anymore so it won't find it
            # but will look for the same package_id
            self.client.run("install .", assert_error=True)
            self.assertIn("- Package ID: 3ec60bb399a8bcb937b7af196f6685ba878aab02",
                          self.client.out)

        # Now change the Hello version and build it, if we install out requires is
        # needed the --build needed because Hello2 needs to be build
        self._export("Hello", "1.5.0", package_id_text=None, requires=None)
        self.client.run("install Hello/1.5.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.out)

    def test_version_full_recipe_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)
        pkg_id = "586c42dfdef8986cde85cda46b44133db925baae"
        self.assertIn("Hello2/2.3.8@lasote/stable:{} - Build".format(pkg_id),
                      self.client.out)

        # If we change the user and channel should be needed to rebuild
        self._export("Hello", "1.2.0", package_id_text=None, requires=None,
                     channel="memsharded/testing")
        self.client.run("install Hello/1.2.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.out)

        # If we change only the package ID from hello (one more defaulted option
        #  to True) should not affect
        self._export("Hello", "1.2.0", package_id_text=None, requires=None,
                     default_option_value='"on"')
        self.client.run("install Hello/1.2.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)

        assert_error = True if self.client.cache.config.revisions_enabled else False
        self.client.run("install .", assert_error=assert_error)
        self.assertIn("Hello2/2.3.8@lasote/stable:{}".format(pkg_id), self.client.out)

    def test_version_full_package_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_package_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change only the package ID from hello (one more defaulted option
        #  to True) should affect
        self._export("Hello", "1.2.0", package_id_text=None, requires=None,
                     default_option_value='"on"')
        self.client.run("install Hello/1.2.0@lasote/stable --build missing")
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.out)
        self.assertIn("Package ID:", self.client.out)

    def test_nameless_mode(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].unrelated_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change even the require, should not affect
        self._export("HelloNew", "1.2.0")
        self.client.run("install HelloNew/1.2.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["HelloNew"].unrelated_mode()',
                     requires=["HelloNew/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"},
                         clean_first=True)
        # Not needed to rebuild Hello2, it doesn't matter its requires
        if not self.client.cache.config.revisions_enabled:
            self.client.run("install .")
        else:  # We have changed hello2, so a new binary is required, but same id
            self.client.run("install .", assert_error=True)
            self.assertIn("The package "
                          "Hello2/2.3.8@lasote/stable:0c8b5ebf2790dd989f84360c366965b731a9bfc8 "
                          "doesn't belong to the installed recipe revision, removing folder",
                          self.client.out)
            self.assertIn("Hello2/2.3.8@lasote/stable:0c8b5ebf2790dd989f84360c366965b731a9bfc8 -"
                          " Missing", self.client.out)

    def test_toolset_visual_compatibility(self):
        # By default is the same to build with native visual or the toolchain
        for package_id in [None, "self.info.vs_toolset_compatible()"]:
            self._export("Hello", "1.2.0", package_id_text=package_id,
                         channel="user/testing",
                         settings=["compiler", ])
            self.client.run('install Hello/1.2.0@user/testing '
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=14 --build')

            # Should have binary available
            self.client.run('install Hello/1.2.0@user/testing'
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=15 -s compiler.toolset=v140')

            # Should NOT have binary available
            self.client.run('install Hello/1.2.0@user/testing '
                            '-s compiler="Visual Studio" '
                            '-s compiler.version=15 -s compiler.toolset=v120',
                            assert_error=True)

            self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

            # Specify a toolset not involved with the visual version is ok, needed to build:
            self.client.run('install Hello/1.2.0@user/testing'
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=15 -s compiler.toolset=v141_clang_c2 '
                            '--build missing')

    def test_toolset_visual_incompatibility(self):
        # By default is the same to build with native visual or the toolchain
        self._export("Hello", "1.2.0", package_id_text="self.info.vs_toolset_incompatible()",
                     channel="user/testing",
                     settings=["compiler", ],
                     )
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="Visual Studio" '
                        ' -s compiler.version=14 --build')

        # Should NOT have binary available
        self.client.run('install Hello/1.2.0@user/testing'
                        ' -s compiler="Visual Studio" '
                        ' -s compiler.version=15 -s compiler.toolset=v140',
                        assert_error=True)
        self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

    def test_build_settings(self):

        def install_and_get_info(package_id_text):
            self.client.run("remove * -f")
            self._export("Hello", "1.2.0", package_id_text=package_id_text,
                         channel="user/testing",
                         settings=["os", "os_build", "arch", "arch_build"])
            self.client.run('install Hello/1.2.0@user/testing '
                            ' -s os="Windows" '
                            ' -s os_build="Linux"'
                            ' -s arch="x86_64"'
                            ' -s arch_build="x86"'
                            ' --build missing')

            hello_ref = ConanFileReference.loads("Hello/1.2.0@user/testing")
            layout = self.client.cache.package_layout(hello_ref)
            pkg_ids = layout.package_ids()
            hello_pref = PackageReference(hello_ref, pkg_ids[0])
            return ConanInfo.loads(load(os.path.join(layout.package(hello_pref), CONANINFO)))

        info = install_and_get_info(None)  # Default

        self.assertEqual(str(info.settings.os_build), "None")
        self.assertEqual(str(info.settings.arch_build), "None")

        # Package has to be present with only os and arch settings
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s os="Windows" '
                        ' -s arch="x86_64"')

        # Even with wrong build settings
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s os="Windows" '
                        ' -s arch="x86_64"'
                        ' -s os_build="Macos"'
                        ' -s arch_build="x86_64"')

        # take into account build
        info = install_and_get_info("self.info.include_build_settings()")
        self.assertEqual(str(info.settings.os_build), "Linux")
        self.assertEqual(str(info.settings.arch_build), "x86")

        # Now the build settings matter
        err = self.client.run('install Hello/1.2.0@user/testing '
                              ' -s os="Windows" '
                              ' -s arch="x86_64"'
                              ' -s os_build="Macos"'
                              ' -s arch_build="x86_64"', assert_error=True)
        self.assertTrue(err)
        self.assertIn("Can't find", self.client.out)

        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s os="Windows" '
                        ' -s arch="x86_64"'
                        ' -s os_build="Linux"'
                        ' -s arch_build="x86"')

        # Now only settings for build
        self.client.run("remove * -f")
        self._export("Hello", "1.2.0",
                     channel="user/testing",
                     settings=["os_build", "arch_build"])
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s os_build="Linux"'
                        ' -s arch_build="x86"'
                        ' --build missing')
        ref = ConanFileReference.loads("Hello/1.2.0@user/testing")
        pkg = os.listdir(self.client.cache.package_layout(ref).packages())
        pref = PackageReference(ref, pkg[0])
        pkg_folder = self.client.cache.package_layout(pref.ref).package(pref)
        info = ConanInfo.loads(load(os.path.join(pkg_folder, CONANINFO)))
        self.assertEqual(str(info.settings.os_build), "Linux")
        self.assertEqual(str(info.settings.arch_build), "x86")

    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="No sense with revs")
    def test_standard_version_default_matching(self):
        self._export("Hello", "1.2.0",
                     channel="user/testing",
                     settings=["compiler", ])

        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 --build')

        self._export("Hello", "1.2.0",
                     channel="user/testing",
                     settings=["compiler", "cppstd", ])

        self.client.run('info Hello/1.2.0@user/testing  -s compiler="gcc" '
                        '-s compiler.libcxx=libstdc++11  -s compiler.version=7.2 '
                        '-s cppstd=gnu14')

        self.client.run('install Hello/1.2.0@user/testing'
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 -s cppstd=gnu14')  # Default, already built

        # Should NOT have binary available
        self.client.run('install Hello/1.2.0@user/testing'
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 -s cppstd=gnu11',
                        assert_error=True)
        self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

    def test_std_non_matching_with_cppstd(self):
        self._export("Hello", "1.2.0", package_id_text="self.info.default_std_non_matching()",
                     channel="user/testing",
                     settings=["compiler", "cppstd", ]
                     )
        self.client.run('install Hello/1.2.0@user/testing'
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 --build')

        self.client.run('install Hello/1.2.0@user/testing'
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 -s cppstd=gnu14',
                        assert_error=True)  # Default
        self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

    def test_std_non_matching_with_compiler_cppstd(self):
        self._export("Hello", "1.2.0", package_id_text="self.info.default_std_non_matching()",
                     channel="user/testing",
                     settings=["compiler", ]
                     )
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 --build')

        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 -s compiler.cppstd=gnu14', assert_error=True)
        self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

    def test_std_matching_with_compiler_cppstd(self):
        self._export("Hello", "1.2.0", package_id_text="self.info.default_std_matching()",
                     channel="user/testing",
                     settings=["compiler", ]
                     )
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 --build')

        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 -s compiler.cppstd=gnu14')
        self.assertIn("Hello/1.2.0@user/testing: Already installed!", self.client.out)

    def test_package_id_requires_patch_mode(self):
        """ Requirements shown in build missing error, must contains transitive packages
            For this test the follow graph has been used:
            libb <- liba
            libfoo <- libbar
            libc <- libb, libfoo
            libd <- libc
        """

        channel = "user/testing"
        self.client.run("config set general.default_package_id_mode=patch_mode")
        self._export("liba", "0.1.0", channel=channel, package_id_text=None, requires=None)
        self.client.run("create . liba/0.1.0@user/testing")
        self._export("libb", "0.1.0", channel=channel, package_id_text=None,
                     requires=["liba/0.1.0@user/testing"])
        self.client.run("create . libb/0.1.0@user/testing")
        self._export("libbar", "0.1.0", channel=channel, package_id_text=None, requires=None)
        self.client.run("create . libbar/0.1.0@user/testing")
        self._export("libfoo", "0.1.0", channel=channel, package_id_text=None,
                     requires=["libbar/0.1.0@user/testing"])
        self.client.run("create . libfoo/0.1.0@user/testing")
        self._export("libc", "0.1.0", channel=channel, package_id_text=None,
                     requires=["libb/0.1.0@user/testing", "libfoo/0.1.0@user/testing"])
        self._export("libd", "0.1.0", channel=channel, package_id_text=None,
                     requires=["libc/0.1.0@user/testing"])
        self.client.run("create . libd/0.1.0@user/testing", assert_error=True)
        self.assertIn("""ERROR: Missing binary: libc/0.1.0@user/testing:e12c9d31fa508340bb8d0c4f9dd4c98a5d0ac082

libc/0.1.0@user/testing: WARN: Can't find a 'libc/0.1.0@user/testing' package for the specified settings, options and dependencies:
- Settings:%s
- Options: an_option=off, liba:an_option=off, libb:an_option=off, libbar:an_option=off, libfoo:an_option=off
- Dependencies: libb/0.1.0@user/testing, libfoo/0.1.0@user/testing
- Requirements: liba/0.1.0, libb/0.1.0, libbar/0.1.0, libfoo/0.1.0
- Package ID: e12c9d31fa508340bb8d0c4f9dd4c98a5d0ac082

ERROR: Missing prebuilt package for 'libc/0.1.0@user/testing'""" % " ", self.client.out)


class PackageIDErrorTest(unittest.TestCase):

    def test_transitive_multi_mode_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        client.run("config set general.full_transitive_package_id=True")
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . dep1/1.0@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")})
        client.run("export . dep2/1.0@user/testing")

        pkg_revision_mode = "self.info.requires.package_revision_mode()"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                                                   .with_package_id(pkg_revision_mode)})
        client.run("export . dep3/1.0@user/testing")

        client.save({"conanfile.py": GenConanfile().with_require("dep2/1.0@user/testing")
                                                   .with_require("dep3/1.0@user/testing")})
        client.run('create . consumer/1.0@user/testing --build')
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    def test_transitive_multi_mode2_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        # This is mandatory, otherwise it doesn't work
        client.run("config set general.full_transitive_package_id=True")

        client.save({"conanfile.py": GenConanfile()})
        client.run("export . dep1/1.0@user/testing")

        pkg_revision_mode = "self.info.requires.full_version_mode()"
        package_id_print = "self.output.info('PkgNames: %s' % sorted(self.info.requires.pkg_names))"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                    .with_package_id(pkg_revision_mode)
                    .with_package_id(package_id_print)})
        client.run("export . dep2/1.0@user/testing")

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . consumer/1.0@user/testing --build')
        self.assertIn("dep2/1.0@user/testing: PkgNames: ['dep1']", client.out)
        self.assertIn("consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']", client.out)
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    def test_transitive_multi_mode_build_requires(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.run("config set general.full_transitive_package_id=True")

        client.save({"conanfile.py": GenConanfile()})
        client.run("export . dep1/1.0@user/testing")
        client.run("create . tool/1.0@user/testing")

        pkg_revision_mode = "self.info.requires.full_version_mode()"
        package_id_print = "self.output.info('PkgNames: %s' % sorted(self.info.requires.pkg_names))"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                    .with_build_requires("tool/1.0@user/testing")
                    .with_package_id(pkg_revision_mode)
                    .with_package_id(package_id_print)})
        client.run("export . dep2/1.0@user/testing")

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                build_requires = "tool/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . consumer/1.0@user/testing --build')
        self.assertIn("dep2/1.0@user/testing: PkgNames: ['dep1']", client.out)
        self.assertIn("consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']", client.out)
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    def test_package_revision_mode_editable(self):
        # Package revision mode crash when using editables
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.run("config set general.full_transitive_package_id=True")

        client.save({"conanfile.py": GenConanfile()})
        client.run("editable add . dep1/1.0@user/testing")

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")})
        client2.run("export . dep2/1.0@user/testing")

        client2.save({"conanfile.py": GenConanfile().with_require("dep2/1.0@user/testing")})
        client2.run('create . consumer/1.0@user/testing --build')
        self.assertIn("consumer/1.0@user/testing: Created", client2.out)


class PackageRevisionModeTestCase(unittest.TestCase):

    def test_transtive_package_revision_mode(self):
        t = TestClient()
        t.save({
            'package1.py': GenConanfile("pkg1"),
            'package2.py': GenConanfile("pkg2").with_require("pkg1/1.0"),
            'package3.py': textwrap.dedent("""
                from conans import ConanFile
                class Recipe(ConanFile):
                    requires = "pkg2/1.0"
                    def package_id(self):
                        self.info.requires["pkg1"].package_revision_mode()
            """)
        })
        t.run("create package1.py pkg1/1.0@")
        t.run("create package2.py pkg2/1.0@")

        # If we only build pkg1, we get a new packageID for pkg3
        t.run("create package3.py pkg3/1.0@ --build=pkg1", assert_error=True)
        self.assertIn("pkg3/1.0:Package_ID_unknown - Unknown", t.out)
        self.assertIn("pkg3/1.0: Updated ID: 283642385cc7b64ec7b5903f6895107e0848d238", t.out)
        self.assertIn("ERROR: Missing binary: pkg3/1.0:283642385cc7b64ec7b5903f6895107e0848d238",
                      t.out)

        # If we build both, we get the new package
        t.run("create package3.py pkg3/1.0@ --build=pkg1 --build=pkg3")
        self.assertIn("pkg3/1.0:Package_ID_unknown - Unknown", t.out)
        self.assertIn("pkg3/1.0: Updated ID: 283642385cc7b64ec7b5903f6895107e0848d238", t.out)
        self.assertIn("pkg3/1.0: Package '283642385cc7b64ec7b5903f6895107e0848d238' created", t.out)

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_package_revision_mode_download(self):
        t = TestClient(default_server_user=True)
        t.save({
            'package1.py': GenConanfile("pkg1"),
            'package2.py':  textwrap.dedent("""
                from conans import ConanFile
                class Recipe(ConanFile):
                    requires = "pkg1/1.0"
                    def package_id(self):
                        self.info.requires["pkg1"].package_revision_mode()
                """),
            'package3.py': GenConanfile("pkg3").with_require("pkg2/1.0")
        })
        t.run("create package1.py pkg1/1.0@")
        t.run("create package2.py pkg2/1.0@")
        t.run("create package3.py pkg3/1.0@")
        t.run("upload * --all -c")
        t.run("remove * -f")

        # If we build pkg1, we need a new packageID for pkg2
        t.run("install pkg3/1.0@ --build=pkg1")
        self.assertIn("pkg2/1.0:Package_ID_unknown - Unknown", t.out)
        self.assertIn("pkg3/1.0:3ea4b5f291451dab54b09abbf324d99d1f4f8cd7 - Download", t.out)
        self.assertIn("pkg2/1.0: Unknown binary for pkg2/1.0, computing updated ID", t.out)
        self.assertIn("pkg2/1.0: Updated ID: d3afcd43f39697e7529bcc7d1ec5b31c947de74c", t.out)
        self.assertIn("pkg2/1.0: Binary for updated ID from: Download", t.out)
        self.assertIn("pkg2/1.0: Retrieving package d3afcd43f39697e7529bcc7d1ec5b31c947de74c "
                      "from remote 'default'", t.out)
