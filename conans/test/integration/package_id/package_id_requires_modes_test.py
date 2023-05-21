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
        self.client.run("install --requires=hello/1.5.0@lasote/stable --build missing")
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
        self.client.run("install --requires=hello/1.5.0@memsharded/testing --build missing")
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
        self.client.run("install --requires=hello/1.2.0@memsharded/testing --build missing")
        self._export("hello2", "2.3.8", channel="lasote/stable",
                     package_id_text='self.info.requires["hello"].full_version_mode()',
                     requires=["hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        # As we have changed hello2, the binary is not valid anymore so it won't find it
        # but will look for the same package_id
        self.client.run("install .", assert_error=True)
        self.assertIn("ERROR: Missing binary: "
                      "hello2/2.3.8@lasote/stable:971e20f31a0d8deb18f03a0f8f72fd95623a8e29",
                      self.client.out)

        # Now change the Hello version and build it, if we install out requires is
        # needed the --build needed because hello2 needs to be build
        self._export("hello", "1.5.0", package_id_text=None, requires=None, channel="lasote/stable")
        self.client.run("install --requires=hello/1.5.0@lasote/stable --build missing")
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
        self.client.run("install --requires=hello/1.2.0@memsharded/testing --build missing")
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
        self.client.run("install --requires=hello/1.2.0@lasote/stable --build missing")
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
        self.client.run("install --requires=hello/1.2.0@lasote/stable --build missing")
        self.client.save({"conanfile.txt": "[requires]\nhello2/2.3.8@lasote/stable"},
                         clean_first=True)
        with self.assertRaises(Exception):
            self.client.run("install .")
        self.assertIn("Can't find a 'hello2/2.3.8@lasote/stable' package", self.client.out)

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
        self.client.run("install --requires=HelloNew/1.2.0@lasote/stable --build missing")
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

    def test_package_id_requires_patch_mode(self):
        """ Requirements shown in build missing error, must contains transitive packages
            For this test the follow graph has been used:
            libb <- liba
            libfoo <- libbar
            libc <- libb, libfoo
            libd <- libc
        """

        channel = "user/testing"
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
        package_id_missing = "18e1a54bf351cd291da5a01ef545ce338243285f"
        self.assertIn(f"""ERROR: Missing binary: libc/0.1.0@user/testing:{package_id_missing}

libc/0.1.0@user/testing: WARN: Can't find a 'libc/0.1.0@user/testing' package binary '{package_id_missing}' for the configuration:
[options]
an_option=off
[requires]
liba/0.1.0@user/testing
libb/0.1.0@user/testing
libbar/0.1.0@user/testing
libfoo/0.1.0@user/testing""", self.client.out)


class PackageIDErrorTest(unittest.TestCase):

    def test_transitive_multi_mode_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=dep1 --version=1.0 --user=user --channel=testing")
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")})
        client.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        pkg_revision_mode = "self.info.requires.recipe_revision_mode()"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                                                   .with_package_id(pkg_revision_mode)})
        client.run("export . --name=dep3 --version=1.0 --user=user --channel=testing")

        client.save({"conanfile.py": GenConanfile().with_require("dep2/1.0@user/testing")
                                                   .with_require("dep3/1.0@user/testing")})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build=*')
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    def test_transitive_multi_mode2_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
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
            from conan import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build=*')
        self.assertIn("dep2/1.0@user/testing: PkgNames: ['dep1']", client.out)
        self.assertIn("consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']", client.out)
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    def test_transitive_multi_mode_build_requires(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
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
            from conan import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                build_requires = "tool/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build=*')
        self.assertIn("dep2/1.0@user/testing: PkgNames: ['dep1']", client.out)
        self.assertIn("consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']", client.out)
        self.assertIn("consumer/1.0@user/testing: Created", client.out)

    @pytest.mark.xfail(reason="cache2.0 editables not considered yet")
    def test_package_revision_mode_editable(self):
        # Package revision mode crash when using editables
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("editable add . dep1/1.0@user/testing")

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")})
        client2.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        client2.save({"conanfile.py": GenConanfile().with_require("dep2/1.0@user/testing")})
        client2.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build=*')
        self.assertIn("consumer/1.0@user/testing: Created", client2.out)
