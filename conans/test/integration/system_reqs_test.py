import os
import re
import stat
import unittest

import pytest

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient
from conans.util.files import load

base_conanfile = '''
from conans import ConanFile

class TestSystemReqs(ConanFile):
    name = "Test"
    version = "0.1"
    options = {"myopt": [True, False]}
    default_options = {"myopt": True}

    def system_requirements(self):
        self.output.info("*+Running system requirements+*")
        %GLOBAL%
        return "Installed my stuff"
'''


@pytest.mark.xfail(reason="cache2.0: check this for 2.0, nre chache will recreate sys_reqs"
                   "every time")
class SystemReqsTest(unittest.TestCase):
    def test_force_system_reqs_rerun(self):
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        client.run("create . user/channel")
        self.assertIn("*+Running system requirements+*", client.out)
        client.run("install --reference=Test/0.1@user/channel")
        self.assertNotIn("*+Running system requirements+*", client.out)
        ref = RecipeReference.loads("Test/0.1@user/channel")
        pref = client.get_latest_package_reference(ref)
        reqs_file = client.get_latest_pkg_layout(pref).system_reqs_package()
        os.unlink(reqs_file)
        client.run("install --reference=Test/0.1@user/channel")
        self.assertIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(reqs_file))

    def test_local_system_requirements(self):
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        client.run("install .")
        self.assertIn("*+Running system requirements+*", client.out)

        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "self.run('fake command!')")}
        client.save(files)
        with self.assertRaisesRegex(Exception, "Command failed"):
            client.run("install .")

    def test_per_package(self):
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        client.run("export . --user=user --channel=testing")
        client.run("install --reference=Test/0.1@user/testing --build missing")
        package_id = re.search(r"Test/0.1@user/testing:(\S+)", str(client.out)).group(1)
        self.assertIn("*+Running system requirements+*", client.out)
        ref = RecipeReference.loads("Test/0.1@user/testing")
        pref = PkgReference(ref, package_id)
        pkg_layout = client.get_latest_pkg_layout(pref)
        self.assertFalse(os.path.exists(pkg_layout.system_reqs()))
        load_file = load(pkg_layout.system_reqs_package())
        self.assertIn("Installed my stuff", load_file)

        # Run again
        client.run("install --reference=Test/0.1@user/testing --build missing")
        pkg_layout = client.get_latest_pkg_layout(pref)
        self.assertNotIn("*+Running system requirements+*", client.out)
        self.assertFalse(os.path.exists(pkg_layout.system_reqs()))
        load_file = load(pkg_layout.system_reqs_package())
        self.assertIn("Installed my stuff", load_file)

        # Run with different option
        client.run("install --reference=Test/0.1@user/testing -o myopt=False --build missing")
        pref2 = PkgReference(ref, NO_SETTINGS_PACKAGE_ID)
        pkg_layout = client.get_latest_pkg_layout(pref)
        pkg_layout2 = client.get_latest_pkg_layout(pref2)
        self.assertIn("*+Running system requirements+*", client.out)
        self.assertFalse(os.path.exists(pkg_layout.system_reqs()))
        load_file = load(pkg_layout2.system_reqs_package())
        self.assertIn("Installed my stuff", load_file)

        # remove packages
        client.run("remove Test* -f -p 544")
        layout1 = client.get_latest_pkg_layout(pref)
        layout2 = client.get_latest_pkg_layout(pref2)
        self.assertTrue(os.path.exists(layout1.system_reqs_package()))
        client.run(f"remove Test* -f -p {package_id}")
        self.assertFalse(os.path.exists(layout1.system_reqs_package()))
        self.assertTrue(os.path.exists(layout2.system_reqs_package()))
        client.run("remove Test* -f -p %s" % NO_SETTINGS_PACKAGE_ID)
        self.assertFalse(os.path.exists(layout1.system_reqs_package()))
        self.assertFalse(os.path.exists(layout2.system_reqs_package()))

    def test_global(self):
        client = TestClient()
        files = {
            'conanfile.py': base_conanfile.replace("%GLOBAL%",
                                                   "self.global_system_requirements=True")
        }
        client.save(files)
        client.run("export . --user=user --channel=testing")
        client.run("install --reference=Test/0.1@user/testing --build missing")
        self.assertIn("*+Running system requirements+*", client.out)
        ref = RecipeReference.loads("Test/0.1@user/testing")
        pref = PkgReference(ref, "a527106fd9f2e3738a55b02087c20c0a63afce9d")
        pkg_layout = client.get_latest_pkg_layout(pref)
        self.assertFalse(os.path.exists(pkg_layout.system_reqs_package()))
        load_file = load(pkg_layout.system_reqs())
        self.assertIn("Installed my stuff", load_file)

        # Run again
        client.run("install --reference=Test/0.1@user/testing --build missing")
        self.assertNotIn("*+Running system requirements+*", client.out)
        pkg_layout = client.get_latest_pkg_layout(pref)
        self.assertFalse(os.path.exists(pkg_layout.system_reqs_package()))
        load_file = load(pkg_layout.system_reqs())
        self.assertIn("Installed my stuff", load_file)

        # Run with different option
        client.run("install --reference=Test/0.1@user/testing -o myopt=False --build missing")
        self.assertNotIn("*+Running system requirements+*", client.out)
        pref2 = PkgReference(ref, "54c9626b48cefa3b819e64316b49d3b1e1a78c26")
        pkg_layout = client.get_latest_pkg_layout(pref)
        pkg_layout2 = client.get_latest_pkg_layout(pref2)
        self.assertFalse(os.path.exists(pkg_layout.system_reqs_package()))
        self.assertFalse(os.path.exists(pkg_layout2.system_reqs_package()))
        load_file = load(pkg_layout.system_reqs())
        self.assertIn("Installed my stuff", load_file)

        # remove packages
        client.run("remove Test* -f -p")
        pkg_layout = client.get_latest_pkg_layout(pref)
        pkg_layout2 = client.get_latest_pkg_layout(pref2)
        self.assertFalse(os.path.exists(pkg_layout.system_reqs_package()))
        self.assertFalse(os.path.exists(pkg_layout2.system_reqs_package()))
        self.assertFalse(os.path.exists(pkg_layout.system_reqs()))

    def test_wrong_output(self):
        client = TestClient()
        files = {
            'conanfile.py':
            base_conanfile.replace("%GLOBAL%", "").replace('"Installed my stuff"', 'None')
        }
        client.save(files)
        client.run("export . --user=user --channel=testing")
        client.run("install --reference=Test/0.1@user/testing --build missing")
        package_id = re.search(r"Test/0.1@user/testing:(\S+)", str(client.out)).group(1)

        self.assertIn("*+Running system requirements+*", client.out)
        ref = RecipeReference.loads("Test/0.1@user/testing")
        self.assertFalse(os.path.exists(client.cache.package_layout(ref).system_reqs()))
        pref = PkgReference(ref, package_id)
        load_file = load(client.cache.package_layout(pref.ref).system_reqs_package(pref))
        self.assertEqual('', load_file)

    def test_remove_system_reqs(self):
        ref = RecipeReference.loads("Test/0.1@user/channel")
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        pref = client.get_latest_package_reference(ref)
        system_reqs_path = os.path.dirname(client.get_latest_pkg_layout(pref).system_reqs())

        # create package to populate system_reqs folder
        self.assertFalse(os.path.exists(system_reqs_path))
        client.run("create . user/channel")
        self.assertIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(system_reqs_path))

        # a new build must not remove or re-run
        client.run("create . user/channel")
        self.assertNotIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(system_reqs_path))

        # remove system_reqs global
        client.run("remove --system-reqs Test/0.1@user/channel")
        self.assertIn("Cache system_reqs from Test/0.1@user/channel has been removed",
                      client.out)
        self.assertFalse(os.path.exists(system_reqs_path))

        # re-create system_reqs folder
        client.run("create . user/channel")
        self.assertIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(system_reqs_path))

        # Wildcard system_reqs removal
        ref_other = RecipeReference.loads("Test/0.1@user/channel_other")
        pref_other = client.get_latest_package_reference(ref_other)
        system_reqs_path_other = os.path.dirname(client.get_latest_pkg_layout(pref_other).system_reqs())

        client.run("create . user/channel_other")
        client.run("remove --system-reqs '*'")
        self.assertIn("Cache system_reqs from Test/0.1@user/channel has been removed",
                      client.out)
        self.assertIn("Cache system_reqs from Test/0.1@user/channel_other has been removed",
                      client.out)
        self.assertFalse(os.path.exists(system_reqs_path))
        self.assertFalse(os.path.exists(system_reqs_path_other))

        # Check that wildcard isn't triggered randomly
        client.run("create . user/channel_other")
        client.run("remove --system-reqs Test/0.1@user/channel")
        self.assertIn("Cache system_reqs from Test/0.1@user/channel has been removed",
                      client.out)
        self.assertNotIn("Cache system_reqs from Test/0.1@user/channel_other has been removed",
                         client.out)
        self.assertFalse(os.path.exists(system_reqs_path))
        self.assertTrue(os.path.exists(system_reqs_path_other))

        # Check partial wildcard
        client.run("create . user/channel")
        client.run("remove --system-reqs Test/0.1@user/channel_*")
        self.assertNotIn("Cache system_reqs from Test/0.1@user/channel has been removed",
                         client.out)
        self.assertIn("Cache system_reqs from Test/0.1@user/channel_other has been removed",
                      client.out)
        self.assertTrue(os.path.exists(system_reqs_path))
        self.assertFalse(os.path.exists(system_reqs_path_other))

    def test_invalid_remove_reqs(self):
        client = TestClient()

        with self.assertRaisesRegex(Exception,
                                   "ERROR: Please specify a valid pattern or reference to be cleaned"):
            client.run("remove --system-reqs")

        # wrong file reference should be treated as error
        with self.assertRaisesRegex(Exception, "ERROR: Unable to remove system_reqs: "
                                   "foo/version@bar/testing does not exist"):
            client.run("remove --system-reqs foo/version@bar/testing")

        # package is not supported with system_reqs
        with self.assertRaisesRegex(Exception, "ERROR: '-t' and '-p' parameters "
                                   "can't be used at the same time"):
            client.run("remove --system-reqs foo/bar@foo/bar "
                       "-p f0ba3ca2c218df4a877080ba99b65834b9413798")

    def test_permission_denied_remove_system_reqs(self):
        ref = RecipeReference.loads("Test/0.1@user/channel")
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        pref = client.get_latest_package_reference(ref)
        system_reqs_path = os.path.dirname(client.get_latest_pkg_layout(pref).system_reqs())

        # create package to populate system_reqs folder
        self.assertFalse(os.path.exists(system_reqs_path))
        client.run("create . user/channel")
        self.assertIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(system_reqs_path))

        # remove write permission
        current = stat.S_IMODE(os.lstat(system_reqs_path).st_mode)
        os.chmod(system_reqs_path, current & ~stat.S_IWRITE)

        # friendly message for permission error
        with self.assertRaisesRegex(Exception, "ERROR: Unable to remove system_reqs:"):
            client.run("remove --system-reqs Test/0.1@user/channel")
        self.assertTrue(os.path.exists(system_reqs_path))

        # restore write permission so the temporal folder can be deleted later
        os.chmod(system_reqs_path, current | stat.S_IWRITE)

    def test_duplicate_remove_system_reqs(self):
        ref = RecipeReference.loads("Test/0.1@user/channel")
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        pref = client.get_latest_package_reference(ref)
        system_reqs_path = os.path.dirname(client.get_latest_pkg_layout(pref).system_reqs())

        # create package to populate system_reqs folder
        self.assertFalse(os.path.exists(system_reqs_path))
        client.run("create . user/channel")
        self.assertIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(system_reqs_path))

        # a new build must not remove or re-run
        client.run("create . user/channel")
        self.assertNotIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(system_reqs_path))

        # remove system_reqs global
        client.run("remove --system-reqs Test/0.1@user/channel")
        self.assertIn("Cache system_reqs from Test/0.1@user/channel has been removed",
                      client.out)
        self.assertFalse(os.path.exists(system_reqs_path))

        # try to remove system_reqs global again
        client.run("remove --system-reqs Test/0.1@user/channel")
        self.assertIn("Cache system_reqs from Test/0.1@user/channel has been removed",
                      client.out)
        self.assertFalse(os.path.exists(system_reqs_path))

        # re-create system_reqs folder
        client.run("create . user/channel")
        self.assertIn("*+Running system requirements+*", client.out)
        self.assertTrue(os.path.exists(system_reqs_path))
