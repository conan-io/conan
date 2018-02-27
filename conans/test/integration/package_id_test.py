import unittest

from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient
from conans.util.files import load
from conans.paths import CONANINFO
import os
from conans.test.utils.conanfile import TestConanFile


class PackageIDTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def cross_build_settings_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "arch", "compiler", "os_build", "arch_build"
        """
        client.save({"conanfile.py": conanfile})
        client.run('install . -s os=Windows -s compiler="Visual Studio" '
                   '-s compiler.version=15 -s compiler.runtime=MD '
                   '-s os_build=Windows -s arch_build=x86 -s compiler.toolset=v141')
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertNotIn("compiler.toolset=None", conaninfo)
        self.assertNotIn("os_build=None", conaninfo)
        self.assertNotIn("arch_build=None", conaninfo)

    def _export(self, name, version, package_id_text=None, requires=None,
                channel=None, default_option_value="off", settings=None):
        conanfile = TestConanFile(name, version, requires=requires,
                                  options={"an_option": ["on", "off"]},
                                  default_options=[("an_option", "%s" % default_option_value)],
                                  package_id=package_id_text,
                                  settings=settings)

        self.client.save({"conanfile.py": str(conanfile)}, clean_first=True)
        self.client.run("export . %s" % (channel or "lasote/stable"))

    @property
    def conaninfo(self):
        return load(os.path.join(self.client.current_folder, CONANINFO))

    def test_version_semver_schema(self):
        self._export("Hello", "1.2.0")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.Y.Z", [line.strip() for line in self.conaninfo.splitlines()])

        # Now change the Hello version and build it, if we install out requires should not be
        # needed the --build needed because Hello2 don't need to be rebuilt
        self._export("Hello", "1.5.0", package_id_text=None, requires=None)
        self.client.run("install Hello/1.5.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("Hello2/2.Y.Z", [line.strip() for line in self.conaninfo.splitlines()])

        # Try to change user and channel too, should be the same, not rebuilt needed
        self._export("Hello", "1.5.0", package_id_text=None, requires=None, channel="memsharded/testing")
        self.client.run("install Hello/1.5.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.5.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("Hello2/2.Y.Z", [line.strip() for line in self.conaninfo.splitlines()])

    def test_version_full_version_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change the user and channel should not be needed to rebuild
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, channel="memsharded/testing")
        self.client.run("install Hello/1.2.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # Now change the Hello version and build it, if we install out requires is
        # needed the --build needed because Hello2 needs to be build
        self._export("Hello", "1.5.0", package_id_text=None, requires=None)
        self.client.run("install Hello/1.5.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.user_io.out)

    def test_version_full_recipe_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change the user and channel should be needed to rebuild
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, channel="memsharded/testing")
        self.client.run("install Hello/1.2.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.user_io.out)

        # If we change only the package ID from hello (one more defaulted option to True) should not affect
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, default_option_value="on")
        self.client.run("install Hello/1.2.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)

        self.client.run("install .")

    def test_version_full_package_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_package_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change only the package ID from hello (one more defaulted option to True) should affect
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, default_option_value="on")
        self.client.run("install Hello/1.2.0@lasote/stable --build missing")
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.user_io.out)
        self.assertIn("Package ID:", self.client.user_io.out)

    def test_nameless_mode(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].unrelated_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install . --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change even the require, should not affect
        self._export("HelloNew", "1.2.0")
        self.client.run("install HelloNew/1.2.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["HelloNew"].unrelated_mode()',
                     requires=["HelloNew/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        # Not needed to rebuild Hello2, it doesn't matter its requires
        self.client.run("install .")

    def test_toolset_visual_compatibility(self):
        # By default is the same to build with native visual or the toolchain
        for package_id in [None, "self.info.vs_toolset_compatible()"]:
            self._export("Hello", "1.2.0", package_id_text=package_id,
                         channel="user/testing",
                         settings='"compiler"')
            self.client.run('install Hello/1.2.0@user/testing '
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=14 --build')

            # Should have binary available
            self.client.run('install Hello/1.2.0@user/testing'
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=15 -s compiler.toolset=v140')

            # Should NOT have binary available
            error = self.client.run('install Hello/1.2.0@user/testing '
                                    '-s compiler="Visual Studio" '
                                    '-s compiler.version=15 -s compiler.toolset=v120',
                                    ignore_error=True)
            self.assertTrue(error)
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
                     settings='"compiler"',
                     )
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="Visual Studio" '
                        ' -s compiler.version=14 --build')

        # Should NOT have binary available
        error = self.client.run('install Hello/1.2.0@user/testing'
                                ' -s compiler="Visual Studio" '
                                ' -s compiler.version=15 -s compiler.toolset=v140',
                                ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

    def test_build_settings(self):

        def install_and_get_info(package_id_text):
            self.client.run("remove * -f")
            self._export("Hello", "1.2.0", package_id_text=package_id_text,
                         channel="user/testing",
                         settings='"os", "os_build", "arch", "arch_build"')
            self.client.run('install Hello/1.2.0@user/testing '
                            ' -s os="Windows" '
                            ' -s os_build="Linux"'
                            ' -s arch="x86_64"'
                            ' -s arch_build="x86"'
                            ' --build missing')

            ref = ConanFileReference.loads("Hello/1.2.0@user/testing")
            pkg = os.listdir(self.client.client_cache.packages(ref))
            pid = PackageReference(ref, pkg[0])
            pkg_folder = self.client.client_cache.package(pid)
            return ConanInfo.loads(load(os.path.join(pkg_folder, CONANINFO)))

        info = install_and_get_info(None)  # Default

        self.assertEquals(str(info.settings.os_build), "None")
        self.assertEquals(str(info.settings.arch_build), "None")

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
        self.assertEquals(str(info.settings.os_build), "Linux")
        self.assertEquals(str(info.settings.arch_build), "x86")

        # Now the build settings matter
        err = self.client.run('install Hello/1.2.0@user/testing '
                              ' -s os="Windows" '
                              ' -s arch="x86_64"'
                              ' -s os_build="Macos"'
                              ' -s arch_build="x86_64"', ignore_error=True)
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
                     settings='"os_build", "arch_build"')
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s os_build="Linux"'
                        ' -s arch_build="x86"'
                        ' --build missing')
        ref = ConanFileReference.loads("Hello/1.2.0@user/testing")
        pkg = os.listdir(self.client.client_cache.packages(ref))
        pid = PackageReference(ref, pkg[0])
        pkg_folder = self.client.client_cache.package(pid)
        info = ConanInfo.loads(load(os.path.join(pkg_folder, CONANINFO)))
        self.assertEquals(str(info.settings.os_build), "Linux")
        self.assertEquals(str(info.settings.arch_build), "x86")

    def test_standard_version_default_matching(self):
        self._export("Hello", "1.2.0",
                     channel="user/testing",
                     settings='"compiler"')

        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 --build')

        self._export("Hello", "1.2.0",
                     channel="user/testing",
                     settings='"compiler", "cppstd"')

        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 -s cppstd=gnu14')  # Default, already built

        # Should NOT have binary available
        error = self.client.run('install Hello/1.2.0@user/testing'
                                ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                                ' -s compiler.version=7.2 -s cppstd=gnu11',
                                ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

    def test_standard_version_default_non_matching(self):
        self._export("Hello", "1.2.0", package_id_text="self.info.default_std_non_matching()",
                     channel="user/testing",
                     settings='"compiler"'
                     )
        self.client.run('install Hello/1.2.0@user/testing '
                        ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                        ' -s compiler.version=7.2 --build')

        self._export("Hello", "1.2.0", package_id_text="self.info.default_std_non_matching()",
                     channel="user/testing",
                     settings='"compiler", "cppstd"'
                     )
        error = self.client.run('install Hello/1.2.0@user/testing '
                                ' -s compiler="gcc" -s compiler.libcxx=libstdc++11'
                                ' -s compiler.version=7.2 -s cppstd=gnu14',
                                ignore_error=True)  # Default
        self.assertTrue(error)
        self.assertIn("Missing prebuilt package for 'Hello/1.2.0@user/testing'", self.client.out)

