# coding=utf-8
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class CreateEditablePackageTest(unittest.TestCase):

    conanfile_base = textwrap.dedent("""\
        from conans import ConanFile

        class APck(ConanFile):
            {body}
        """)
    conanfile = conanfile_base.format(body="pass")

    conan_package_layout = textwrap.dedent("""\
        [includedirs]
        src/include
        """)

    def test_link_wrong_layout(self):
        ref = ConanFileReference.loads('lib/version@user/name')
        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile, "mylayout": ""})
        t.run('editable add . {} --layout=missing'.format(ref), assert_error=True)
        self.assertIn("ERROR: Couldn't find layout file: missing", t.out)

    def test_install_ok(self):
        ref = ConanFileReference.loads('lib/version@user/name')
        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile})
        t.run('editable add . {}'.format(ref))
        self.assertIn("Reference 'lib/version@user/name' in editable mode", t.out)

    def test_editable_list_search(self):
        ref = ConanFileReference.loads('lib/version@user/name')
        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile})
        t.run('editable add . {}'.format(ref))
        t.run("editable list")
        self.assertIn("lib/version@user/name", t.out)
        self.assertIn("    Layout: None", t.out)
        self.assertIn("    Path:", t.out)

        t.run("search")
        self.assertIn("lib/version@user/name", t.out)

    def test_install_wrong_reference(self):
        ref = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': textwrap.dedent("""\
            from conans import ConanFile

            class Pck(ConanFile):
                name = "lib"
                version = "version"
            """)})
        t.run('export  . {}'.format(ref))
        t.run('editable add . wrong/version@user/channel', assert_error=True)
        self.assertIn("ERROR: Name and version from reference (wrong/version@user/channel) and "
                      "target conanfile.py (lib/version) must match", t.out)

    def missing_subarguments_test(self):
        t = TestClient()
        t.run("editable", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", t.out)
