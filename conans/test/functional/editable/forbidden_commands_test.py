# coding=utf-8

import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer


class ForbiddenRemoveTest(unittest.TestCase):

    def test_remove(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class APck(ConanFile):
                pass
            """)
        ref = ConanFileReference.loads('lib/version@user/name')
        t = TestClient()
        t.save(files={'conanfile.py': conanfile,
                      "mylayout": "", })
        t.run("export . lib/version@user/name")
        t.run('editable add . {}'.format(ref))
        self.assertTrue(t.cache.installed_as_editable(ref))
        t.run('remove {} --force'.format(ref), assert_error=True)
        self.assertIn("Package 'lib/version@user/name' is installed as editable, remove it first "
                      "using command 'conan editable remove lib/version@user/name'", t.out)

        # Also with a pattern, but only a warning
        t.run('remove lib* --force')
        self.assertIn("WARN: Package 'lib/version@user/name' is installed as editable, "
                      "remove it first using command 'conan editable remove lib/version@user/name'",
                      t.out)
        self.assertTrue(t.cache.installed_as_editable(ref))


class ForbiddenCommandsTest(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class APck(ConanFile):
            pass
        """)

    def setUp(self):
        self.ref = ConanFileReference.loads('lib/version@user/name')

        test_server = TestServer()
        self.servers = {"default": test_server}
        self.t = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self.t.save(files={'conanfile.py': self.conanfile,
                           "mylayout": "", })
        self.t.run('editable add . {}'.format(self.ref))
        self.assertTrue(self.t.cache.installed_as_editable(self.ref))

    def test_export(self):
        self.t.run('export . {}'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    def test_create(self):
        self.t.run('create . {}'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    def test_create_update(self):
        self.t.run('create . {} --update'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    def test_upload(self):
        self.t.run('upload --force {}'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    def test_export_pkg(self):
        self.t.run('export-pkg -f . {}'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)

    def test_copy(self):
        self.t.run('copy --force {} ouser/ochannel'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)
