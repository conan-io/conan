import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, GenConanfile


# TODO: Fix tests with local methods
class PackageIDTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

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
                conanfile = conanfile.with_require(RecipeReference.loads(require))

        self.client.save({"conanfile.py": str(conanfile)}, clean_first=True)
        if channel:
            user, channel = channel.split("/")
            self.client.run(f"export . --user={user} --channel={channel}")
        else:
            self.client.run("export .")

    @pytest.mark.xfail(reason="cache2.0 revisit this for 2.0")
    def test_version_semver_schema(self):
        self._export("hello", "1.2.0")
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["hello"].semver()',
                     requires=["hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")

        # Now change the Hello version and build it, if we install out requires should not be
        # needed the --build needed because hello2 don't need to be rebuilt
        self._export("hello", "1.5.0", package_id_text=None, requires=None)
        self.client.run("install --reference=hello/1.5.0@lasote/stable --build missing")
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["hello"].semver()',
                     requires=["hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)

        # As we have changed hello2, the binary is not valid anymore so it won't find it
        # but will look for the same package_id
        self.client.run("install .", assert_error=True)
        self.assertIn("WARN: The package hello2/2.3.8@lasote/stable:"
                      "dce86675f75d209098577f160da7413aed767d0d doesn't belong to the "
                      "installed recipe revision, removing folder",
                      self.client.out)
        self.assertIn("- Package ID: dce86675f75d209098577f160da7413aed767d0d",
                      self.client.out)

        # Try to change user and channel too, should be the same, not rebuilt needed
        self._export("hello", "1.5.0", package_id_text=None, requires=None,
                     channel="memsharded/testing")
        self.client.run("install --reference=hello/1.5.0@memsharded/testing --build missing")
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["hello"].semver()',
                     requires=["hello/1.5.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)

        self.client.run("install .", assert_error=True)
        self.assertIn("hello2/2.3.8@lasote/stable:dce86675f75d209098577f160da7413aed767d0d",
                      self.client.out)

    def test_version_full_version_schema(self):
        self._export("hello", "1.2.0", package_id_text=None, requires=None, channel="lasote/stable")
        self._export("hello2", "2.3.8", channel="lasote/stable",
                     package_id_text='self.info.requires["hello"].full_version_mode()',
                     requires=["hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")

        # If we change the user and channel should not be needed to rebuild
        self._export("hello", "1.2.0", package_id_text=None, requires=None,
                     channel="memsharded/testing")
        self.client.run("install --reference=hello/1.2.0@memsharded/testing --build missing")
        self._export("hello2", "2.3.8", channel="lasote/stable",
                     package_id_text='self.info.requires["hello"].full_version_mode()',
                     requires=["hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        # As we have changed hello2, the binary is not valid anymore so it won't find it
        # but will look for the same package_id
        self.client.run("install .", assert_error=True)
        self.assertIn("- Package ID: d63d347db2ab3bd76ef72e56a330887d35d658be",
                      self.client.out)

        # Now change the Hello version and build it, if we install out requires is
        # needed the --build needed because hello2 needs to be build
        self._export("hello", "1.5.0", package_id_text=None, requires=None, channel="lasote/stable")
        self.client.run("install --reference=hello/1.5.0@lasote/stable --build missing")
        self._export("hello2", "2.3.8", channel="lasote/stable",
                     package_id_text='self.info.requires["hello"].full_version_mode()',
                     requires=["hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'hello2/2.3.8@lasote/stable' package", self.client.out)

    @pytest.mark.xfail(reason="cache2.0 revisit this for 2.0")
    def test_version_full_recipe_schema(self):
        self._export("hello", "1.2.0", package_id_text=None, requires=None)
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["hello"].full_recipe_mode()',
                     requires=["hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")

        pkg_id = "e40e4e325977c9f91694ed4c7108979a2d24666d"
        self.assertIn("hello2/2.3.8@lasote/stable:{} - Build".format(pkg_id),
                      self.client.out)

        # If we change the user and channel should be needed to rebuild
        self._export("hello", "1.2.0", package_id_text=None, requires=None,
                     channel="memsharded/testing")
        self.client.run("install --reference=hello/1.2.0@memsharded/testing --build missing")
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["hello"].full_recipe_mode()',
                     requires=["hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'hello2/2.3.8@lasote/stable' package", self.client.out)

        # If we change only the package ID from hello (one more defaulted option
        #  to True) should not affect
        self._export("hello", "1.2.0", package_id_text=None, requires=None,
                     default_option_value='"on"')
        self.client.run("install --reference=hello/1.2.0@lasote/stable --build missing")
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["hello"].full_recipe_mode()',
                     requires=["hello/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)

        self.client.run("install .", assert_error=True)
        self.assertIn("hello2/2.3.8@lasote/stable:{}".format(pkg_id), self.client.out)

    def test_version_full_package_schema(self):
        self._export("hello", "1.2.0", package_id_text=None, requires=None, channel="lasote/stable")
        self._export("hello2", "2.3.8", channel="lasote/stable",
                     package_id_text='self.info.requires["hello"].full_package_mode()',
                     requires=["hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")

        # If we change only the package ID from hello (one more defaulted option
        #  to True) should affect
        self._export("hello", "1.2.0", package_id_text=None, requires=None, channel="lasote/stable",
                     default_option_value='"on"')
        self.client.run("install --reference=hello/1.2.0@lasote/stable --build missing")
        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'hello2/2.3.8@lasote/stable' package", self.client.out)
        self.assertIn("Package ID:", self.client.out)

    @pytest.mark.xfail(reason="cache2.0 revisit this for 2.0")
    def test_nameless_mode(self):
        self._export("hello", "1.2.0", package_id_text=None, requires=None)
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["hello"].unrelated_mode()',
                     requires=["hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        self.client.run("install . --build missing")

        # If we change even the require, should not affect
        self._export("HelloNew", "1.2.0")
        self.client.run("install --reference=HelloNew/1.2.0@lasote/stable --build missing")
        self._export("hello2", "2.3.8",
                     package_id_text='self.info.requires["HelloNew"].unrelated_mode()',
                     requires=["HelloNew/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        # Not needed to rebuild hello2, it doesn't matter its requires
        # We have changed hello2, so a new binary is required, but same id
        self.client.run("install .", assert_error=True)
        package_id = "cc0975391fddf13e161a63ef63999445df98fb0c"
        self.assertIn("The package "
                      f"hello2/2.3.8@lasote/stable:{package_id} "
                      "doesn't belong to the installed recipe revision, removing folder",
                      self.client.out)
        self.assertIn(f"hello2/2.3.8@lasote/stable:{package_id} -"
                      " Missing", self.client.out)

    def test_toolset_visual_compatibility(self):
        # By default is the same to build with native visual or the toolchain
        for package_id in [None, "self.info.vs_toolset_compatible()"]:
            self._export("hello", "1.2.0", package_id_text=package_id,
                         channel="user/testing",
                         settings=["compiler", ])
            self.client.run('install --reference=hello/1.2.0@user/testing '
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=14 --build')

            # Should have binary available
            self.client.run('install --reference=hello/1.2.0@user/testing'
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=15 -s compiler.toolset=v140')

            # Should NOT have binary available
            self.client.run('install --reference=hello/1.2.0@user/testing '
                            '-s compiler="Visual Studio" '
                            '-s compiler.version=15 -s compiler.toolset=v120',
                            assert_error=True)

            self.assertIn("Missing prebuilt package for 'hello/1.2.0@user/testing'", self.client.out)

            # Specify a toolset not involved with the visual version is ok, needed to build:
            self.client.run('install --reference=hello/1.2.0@user/testing'
                            ' -s compiler="Visual Studio" '
                            ' -s compiler.version=15 -s compiler.toolset=v141_clang_c2 '
                            '--build missing')

    def test_toolset_visual_incompatibility(self):
        # By default is the same to build with native visual or the toolchain
        self._export("hello", "1.2.0", package_id_text="self.info.vs_toolset_incompatible()",
                     channel="user/testing",
                     settings=["compiler", ],
                     )
        self.client.run('install --reference=hello/1.2.0@user/testing '
                        ' -s compiler="Visual Studio" '
                        ' -s compiler.version=14 --build')

        # Should NOT have binary available
        self.client.run('install --reference=hello/1.2.0@user/testing'
                        ' -s compiler="Visual Studio" '
                        ' -s compiler.version=15 -s compiler.toolset=v140',
                        assert_error=True)
        self.assertIn("Missing prebuilt package for 'hello/1.2.0@user/testing'", self.client.out)

    def test_package_id_requires_patch_mode(self):
        """ Requirements shown in build missing error, must contains transitive packages
            For this test the follow graph has been used:
            libb <- liba
            libfoo <- libbar
            libc <- libb, libfoo
            libd <- libc
        """

        channel = "user/testing"
        conan_conf = textwrap.dedent("""
                        [storage]
                        path = ./data
                        [general]
                        default_package_id_mode=patch_mode'
                """.format())
        self.client.save({"conan.conf": conan_conf}, path=self.client.cache.cache_folder)
        self._export("liba", "0.1.0", channel=channel, package_id_text=None, requires=None)
        self.client.run("create . --name=liba --version=0.1.0 --user=user --channel=testing")
        self._export("libb", "0.1.0", channel=channel, package_id_text=None,
                     requires=["liba/0.1.0@user/testing"])
        self.client.run("create . --name=libb --version=0.1.0 --user=user --channel=testing")
        self._export("libbar", "0.1.0", channel=channel, package_id_text=None, requires=None)
        self.client.run("create . --name=libbar --version=0.1.0 --user=user --channel=testing")
        self._export("libfoo", "0.1.0", channel=channel, package_id_text=None,
                     requires=["libbar/0.1.0@user/testing"])
        self.client.run("create . --name=libfoo --version=0.1.0 --user=user --channel=testing")
        self._export("libc", "0.1.0", channel=channel, package_id_text=None,
                     requires=["libb/0.1.0@user/testing", "libfoo/0.1.0@user/testing"])
        self._export("libd", "0.1.0", channel=channel, package_id_text=None,
                     requires=["libc/0.1.0@user/testing"])
        self.client.run("create . --name=libd --version=0.1.0 --user=user --channel=testing", assert_error=True)
        self.assertIn("""ERROR: Missing binary: libc/0.1.0@user/testing:6bc65b4894592ca5f492d000cf2cc793b904c14e

libc/0.1.0@user/testing: WARN: Can't find a 'libc/0.1.0@user/testing' package for the specified settings, options and dependencies:
- Settings:%s
- Options: an_option=off
- Dependencies: libb/0.1.0@user/testing, libfoo/0.1.0@user/testing
- Requirements: liba/0.1.0, libb/0.1.0, libbar/0.1.0, libfoo/0.1.0
- Package ID: 6bc65b4894592ca5f492d000cf2cc793b904c14e""" % " ", self.client.out)


class PackageIDErrorTest(unittest.TestCase):

    def test_transitive_multi_mode_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        conan_conf = textwrap.dedent("""
                        [storage]
                        path = ./data
                        [general]
                        default_package_id_mode=full_package_mode'
                """.format())
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=dep1 --version=1.0 --user=user --channel=testing")
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")})
        client.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        pkg_revision_mode = "self.info.requires.package_revision_mode()"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                                                   .with_package_id(pkg_revision_mode)})
        client.run("export . --name=dep3 --version=1.0 --user=user --channel=testing")

        client.save({"conanfile.py": GenConanfile().with_require("dep2/1.0@user/testing")
                                                   .with_require("dep3/1.0@user/testing")})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build')
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    def test_transitive_multi_mode2_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        conan_conf = textwrap.dedent("""
                        [storage]
                        path = ./data
                        [general]
                        default_package_id_mode=package_revision_mode'
                """.format())
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        # This is mandatory, otherwise it doesn't work
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=dep1 --version=1.0 --user=user --channel=testing")

        pkg_revision_mode = "self.info.requires.full_version_mode()"
        package_id_print = "self.output.info('PkgNames: %s' % sorted(self.info.requires.pkg_names))"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                    .with_package_id(pkg_revision_mode)
                    .with_package_id(package_id_print)})
        client.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build')
        self.assertIn("dep2/1.0@user/testing: PkgNames: ['dep1']", client.out)
        self.assertIn("consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']", client.out)
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    def test_transitive_multi_mode_build_requires(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        conan_conf = textwrap.dedent("""
                        [storage]
                        path = ./data
                        [general]
                        default_package_id_mode=package_revision_mode'
                """.format())
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=dep1 --version=1.0 --user=user --channel=testing")
        client.run("create . --name=tool --version=1.0 --user=user --channel=testing")

        pkg_revision_mode = "self.info.requires.full_version_mode()"
        package_id_print = "self.output.info('PkgNames: %s' % sorted(self.info.requires.pkg_names))"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                    .with_tool_requires("tool/1.0@user/testing")
                    .with_package_id(pkg_revision_mode)
                    .with_package_id(package_id_print)})
        client.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                build_requires = "tool/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build')
        self.assertIn("dep2/1.0@user/testing: PkgNames: ['dep1']", client.out)
        self.assertIn("consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']", client.out)
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    @pytest.mark.xfail(reason="cache2.0 editables not considered yet")
    def test_package_revision_mode_editable(self):
        # Package revision mode crash when using editables
        client = TestClient()
        conan_conf = textwrap.dedent("""
                        [storage]
                        path = ./data
                        [general]
                        default_package_id_mode=package_revision_mode'
                """.format())
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.save({"conanfile.py": GenConanfile()})
        client.run("editable add . dep1/1.0@user/testing")

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")})
        client2.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        client2.save({"conanfile.py": GenConanfile().with_require("dep2/1.0@user/testing")})
        client2.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build')
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
        t.run("create package1.py --name=pkg1 --version=1.0")
        t.run("create package2.py --name=pkg2 --version=1.0")

        # If we only build pkg1, we get a new packageID for pkg3
        t.run("create package3.py --name=pkg3 --version=1.0 --build=pkg1", assert_error=True)
        self.assertIn("pkg3/1.0:Package_ID_unknown - Unknown", t.out)
        self.assertIn("pkg3/1.0: Updated ID: f6770ce9c022ba560312e0efb75c278426f71cbf", t.out)
        self.assertIn("ERROR: Missing binary: pkg3/1.0:f6770ce9c022ba560312e0efb75c278426f71cbf",
                      t.out)

        # If we build both, we get the new package
        t.run("create package3.py --name=pkg3 --version=1.0 --build=pkg1 --build=pkg3")
        self.assertIn("pkg3/1.0:Package_ID_unknown - Unknown", t.out)
        self.assertIn("pkg3/1.0: Updated ID: f6770ce9c022ba560312e0efb75c278426f71cbf", t.out)
        self.assertIn("pkg3/1.0: Package 'f6770ce9c022ba560312e0efb75c278426f71cbf' created", t.out)

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
        t.run("create package1.py --name=pkg1 --version=1.0")
        t.run("create package2.py --name=pkg2 --version=1.0")
        t.run("create package3.py --name=pkg3 --version=1.0")
        t.run("upload * -c -r default")
        t.run("remove * -f")

        # If we build pkg1, we need a new packageID for pkg2
        t.run("install --reference=pkg3/1.0@ --build=pkg1")
        t.assert_listed_binary({"pkg2/1.0": ("Package_ID_unknown", "Unknown"),
                                "pkg3/1.0": ("ad2a3c63a3adc6721aeaac45b34f80f0e1b72827",
                                             "Download (default)")})
        self.assertIn("pkg2/1.0: Unknown binary for pkg2/1.0, computing updated ID", t.out)
        pkg_id = "f1aefa3648a2e2defd70c3ed8c3915061e6c12eb"
        self.assertIn(f"pkg2/1.0: Updated ID: {pkg_id}", t.out)
        self.assertIn("pkg2/1.0: Binary for updated ID from: Download", t.out)
        self.assertIn(f"pkg2/1.0: Retrieving package {pkg_id} from remote 'default'", t.out)
