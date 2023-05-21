import os
import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load

conanfile = """import os
from conan import ConanFile
from conans.util.files import save
from conan.tools.files import copy
class MyTest(ConanFile):
    name = "pkg"
    version = "0.1"
    settings = "os", "build_type"
    build_policy = "missing"
    def build_id(self):
        if self.settings.os == "Windows":
            self.info_build.settings.build_type = "Any"
    def build(self):
        self.output.info("Building my code!")
        save("debug/file1.txt", "Debug file1")
        save("release/file1.txt", "Release file1")
    def package(self):
        self.output.info("Packaging %s!" % self.settings.build_type)
        if self.settings.build_type == "Debug":
            copy(self, "*", os.path.join(self.build_folder, "debug"), self.package_folder,
                 keep_path=False)
        else:
            copy(self, "*", os.path.join(self.build_folder, "release"), self.package_folder,
                 keep_path=False)
"""

consumer = """[requires]
pkg/0.1@user/channel
[imports]
., * -> .
"""

consumer_py = """from conan import ConanFile
class MyTest(ConanFile):
    name = "mytest"
    version = "0.1"
    settings = "os", "build_type"
    requires = "pkg/0.1@user/channel"
    def build_id(self):
        self.info_build.settings.build_type = "Any"
        self.info_build.requires.clear()
"""

package_id_windows_release = "14e27355860f077e112e49068497f4cc531ba8c7"
package_id_windows_debug = "db9edb386f1f47c8c8e08f8f239d73a03313a462"
package_id_linux_release = "c26ded3c7aa4408e7271e458d65421000e000711"
package_id_linux_debug = "5978c0d63d2a428ca63ffb710fa2089b8d2f70c8"


class BuildIdTest(unittest.TestCase):

    def _check_conaninfo(self, client):
        # Check that conaninfo is correct
        latest_rrev = client.cache.get_latest_recipe_reference(RecipeReference.loads("pkg/0.1@user/channel"))
        pref_debug = PkgReference.loads(f"pkg/0.1@user/channel#{latest_rrev.revision}:"
                                        f"{package_id_windows_debug}")
        prev_debug = client.cache.get_latest_package_reference(pref_debug)
        layout = client.cache.pkg_layout(prev_debug)
        conaninfo = load(os.path.join(layout.package(), "conaninfo.txt"))
        self.assertIn("os=Windows", conaninfo)
        self.assertIn("build_type=Debug", conaninfo)
        self.assertNotIn("Release", conaninfo)

        pref_release = PkgReference.loads(f"pkg/0.1@user/channel#{latest_rrev.revision}:"
                                          f"{package_id_windows_release}")
        prev_release = client.cache.get_latest_package_reference(pref_release)
        layout = client.cache.pkg_layout(prev_release)
        conaninfo = load(os.path.join(layout.package(), "conaninfo.txt"))
        self.assertIn("os=Windows", conaninfo)
        self.assertIn("build_type=Release", conaninfo)
        self.assertNotIn("Debug", conaninfo)

        pref_debug = PkgReference.loads(f"pkg/0.1@user/channel#{latest_rrev.revision}:"
                                        f"{package_id_linux_debug}")
        prev_debug = client.cache.get_latest_package_reference(pref_debug)
        layout = client.cache.pkg_layout(prev_debug)
        conaninfo = load(os.path.join(layout.package(), "conaninfo.txt"))
        self.assertIn("os=Linux", conaninfo)
        self.assertIn("build_type=Debug", conaninfo)
        self.assertNotIn("Release", conaninfo)

        pref_release = PkgReference.loads(f"pkg/0.1@user/channel#{latest_rrev.revision}:"f"{package_id_linux_release}")
        prev_release = client.cache.get_latest_package_reference(pref_release)
        layout = client.cache.pkg_layout(prev_release)
        conaninfo = load(os.path.join(layout.package(), "conaninfo.txt"))
        self.assertIn("os=Linux", conaninfo)
        self.assertIn("build_type=Release", conaninfo)
        self.assertNotIn("Debug", conaninfo)

    def test_create(self):
        # Ensure that build_id() works when multiple create calls are made

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . --user=user --channel=channel -s os=Windows -s build_type=Release")
        self.assertIn("pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Building my code!", client.out)
        self.assertIn("Packaging Release!", client.out)
        client.run("create . --user=user --channel=channel -s os=Windows -s build_type=Debug")

        self.assertNotIn("pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Packaging Debug!", client.out)

        client.run("create . --user=user --channel=channel -s os=Linux -s build_type=Release")

        self.assertIn("pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Building my code!", client.out)
        self.assertIn("Packaging Release!", client.out)
        client.run("create . --user=user --channel=channel -s os=Linux -s build_type=Debug")
        self.assertIn("pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Packaging Debug!", client.out)
        self._check_conaninfo(client)

    @parameterized.expand([(True, ), (False,)])
    @pytest.mark.xfail(reason="Remove build folders not implemented yet")
    def test_basic(self, python_consumer):
        client = TestClient()

        client.save({"conanfile.py": conanfile})
        client.run("export . --user=user --channel=channel")
        if python_consumer:
            client.save({"conanfile.py": consumer_py}, clean_first=True)
        else:
            client.save({"conanfile.txt": consumer}, clean_first=True)
        # Windows Debug
        client.run('install . -s os=Windows -s build_type=Debug')
        self.assertIn("Building package from source as defined by build_policy='missing'",
                      client.out)
        self.assertIn("Building my code!", client.out)
        self.assertIn("Packaging Debug!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Debug file1", content)
        # Package Windows Release, it will reuse the previous build
        client.run('install . -s os=Windows -s build_type=Release')
        self.assertNotIn("Building my code!", client.out)
        self.assertIn("Packaging Release!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Release file1", content)

        # Now Linux Debug
        client.run('install . -s os=Linux -s build_type=Debug')
        self.assertIn("Building package from source as defined by build_policy='missing'",
                      client.out)
        self.assertIn("Building my code!", client.out)
        self.assertIn("Packaging Debug!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Debug file1", content)
        # Linux Release must build again, as it is not affected by build_id()
        client.run('install . -s os=Linux -s build_type=Release')
        self.assertIn("Building my code!", client.out)
        self.assertIn("Packaging Release!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Release file1", content)
        self._check_conaninfo(client)

        # TODO: cache2.0 check if we will maintain the remove -p
        # Check that repackaging works, not necessary to re-build
        # client.run("remove pkg/0.1@user/channel -p -c")
        # # Windows Debug
        # client.run('install . -s os=Windows -s build_type=Debug')
        # self.assertNotIn("Building my code!", client.out)
        # self.assertIn("Packaging Debug!", client.out)
        # content = client.load("file1.txt")
        # self.assertEqual("Debug file1", content)
        # # Windows Release
        # client.run('install . -s os=Windows -s build_type=Release')
        # self.assertNotIn("Building my code!", client.out)
        # self.assertIn("Packaging Release!", client.out)
        # content = client.load("file1.txt")
        # self.assertEqual("Release file1", content)
        # # Now Linux
        # client.run('install . -s os=Linux -s build_type=Debug')
        # self.assertIn("Building package from source as defined by build_policy='missing'",
        #               client.out)
        # self.assertIn("Building my code!", client.out)
        # self.assertIn("Packaging Debug!", client.out)
        # content = client.load("file1.txt")
        # self.assertEqual("Debug file1", content)
        # client.run('install . -s os=Linux -s build_type=Release')
        # self.assertIn("Building my code!", client.out)
        # self.assertIn("Packaging Release!", client.out)
        # content = client.load("file1.txt")
        # self.assertEqual("Release file1", content)
        # self._check_conaninfo(client)

        # But if the build folder is removed, the packages are there, do nothing
        client.run("remove pkg/0.1@user/channel -b -c")
        client.run('install . -s os=Windows -s build_type=Debug')
        self.assertNotIn("Building my code!", client.out)
        self.assertNotIn("Packaging Debug!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Windows -s build_type=Release')
        self.assertNotIn("Building my code!", client.out)
        self.assertNotIn("Packaging Release!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Release file1", content)
        # Now Linux
        client.run('install . -s os=Linux -s build_type=Debug')
        self.assertNotIn("Building my code!", client.out)
        self.assertNotIn("Packaging Debug!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Linux -s build_type=Release')
        self.assertNotIn("Building my code!", client.out)
        self.assertNotIn("Packaging Release!", client.out)
        content = client.load("file1.txt")
        self.assertEqual("Release file1", content)
        self._check_conaninfo(client)

    def test_remove_specific_builds(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run('create . --user=user --channel=channel -s os=Windows -s build_type=Debug')
        client.run('create . --user=user --channel=channel -s os=Windows -s build_type=Release')
        ref = RecipeReference.loads("pkg/0.1@user/channel")

        def _check_builds():
            latest_rrev = client.cache.get_latest_recipe_reference(ref)
            pkg_ids = client.cache.get_package_references(latest_rrev)
            prevs = []
            for pkg_id in pkg_ids:
                prevs.extend(client.cache.get_package_revisions_references(pkg_id))
            build_folders = []
            for prev in prevs:
                if os.path.exists(client.cache.pkg_layout(prev).build()):
                    build_folders.append(client.cache.pkg_layout(prev).build())
            self.assertEqual(1, len(build_folders))
            self.assertEqual(2, len(pkg_ids))
            return build_folders[0], pkg_ids

        build, packages = _check_builds()
        # TODO: cache2.0 remove -p and -b is not yet fully implemented
        # we are commenting the first part of this until it is
        #client.run("remove pkg/0.1@user/channel -b %s -c" % packages[0])
        #_check_builds()
        #client.run("remove pkg/0.1@user/channel -b %s -c" % build)
        #cache_builds = client.cache.package_layout(ref).conan_builds()
        #self.assertEqual(0, len(cache_builds))
        #package_ids = client.cache.package_layout(ref).package_ids()
        #self.assertEqual(2, len(package_ids))

    def test_failed_build(self):
        # Repeated failed builds keep failing
        fail_conanfile = textwrap.dedent("""\
            from conan import ConanFile
            class MyTest(ConanFile):
                settings = "build_type"
                def build(self):
                    raise Exception("Failed build!!")
            """)
        client = TestClient()
        # NORMAL case, every create fails
        client.save({"conanfile.py": fail_conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=channel", assert_error=True)
        self.assertIn("ERROR: pkg/0.1@user/channel: Error in build() method, line 5", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=channel", assert_error=True)
        self.assertIn("ERROR: pkg/0.1@user/channel: Error in build() method, line 5", client.out)
        # now test with build_id
        client.save({"conanfile.py": fail_conanfile +
                     "    def build_id(self): self.info_build.settings.build_type = 'any'"})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=channel", assert_error=True)
        self.assertIn("ERROR: pkg/0.1@user/channel: Error in build() method, line 5", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=channel", assert_error=True)
        self.assertIn("ERROR: pkg/0.1@user/channel: Error in build() method, line 5", client.out)


def test_remove_require():
    c = TestClient()
    remove = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "consumer"
            version = "1.0"
            requires = "dep/1.0"
            def build_id(self):
                self.info_build.requires.remove("dep")
        """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "consumer/conanfile.py": remove})
    c.run("create dep")
    c.run("create consumer")
