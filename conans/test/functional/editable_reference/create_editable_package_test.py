# coding=utf-8

import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_editable_layout import CONAN_PACKAGE_LAYOUT_FILE
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

    def test_install_without_deps(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile,
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        t.run('export  . {}'.format(reference))
        t.run('install --editable=. {}'.format(reference))

        self.assertIn("    lib/version@user/name from local cache - Editable", t.out)
        self.assertTrue(t.client_cache.installed_as_editable(reference))
        layout = t.client_cache.package_layout(reference)
        self.assertTrue(layout.installed_as_editable())
        self.assertEqual(layout.conan(), t.current_folder)

    def test_install_with_deps(self):
        ref_parent = ConanFileReference.loads("parent/version@user/name")
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile})
        t.run('create . {}'.format(ref_parent))

        t.save(files={'conanfile.py':
                          self.conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        t.run('export . {}'.format(reference))
        t.run('install --editable=. {}'.format(reference))

        self.assertIn("    lib/version@user/name from local cache - Editable", t.out)
        self.assertTrue(t.client_cache.installed_as_editable(reference))
        layout = t.client_cache.package_layout(reference)
        self.assertTrue(layout.installed_as_editable())
        self.assertEqual(layout.conan(), t.current_folder)

    def test_install_without_package_layout_file(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={os.path.join('conanfile.py'): self.conanfile})
        t.run('export  . {}'.format(reference))
        t.run('install --editable=. {}'.format(reference), assert_error=True)

        self.assertFalse(os.path.exists(CONAN_PACKAGE_LAYOUT_FILE))
        self.assertIn("ERROR: In order to link a package in editable mode, it is required a", t.out)

    def test_install_failed_export_first(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile,
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        t.run('install --editable=. {}'.format(reference), assert_error=True)
        self.assertIn("ERROR: In order to link a package in editable mode, "
                      "its recipe must be already exported to the cache", t.out)
        self.assertFalse(t.client_cache.installed_as_editable(reference))  # Remove editable

    def test_install_failed_deps(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile_base.format(body='requires = "aa/bb@cc/dd"'),
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        t.run('export  . {}'.format(reference))
        t.run('install --editable=. {}'.format(reference), assert_error=True)

        self.assertIn("ERROR: Failed requirement 'aa/bb@cc/dd'", t.out)
        self.assertFalse(t.client_cache.installed_as_editable(reference))  # Remove editable

    def test_install_wrong_reference(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': textwrap.dedent("""\
            from conans import ConanFile
            
            class Pck(ConanFile):
                name = "lib"
                version = "version"
            """)})
        t.run('export  . {}'.format(reference))
        t.run('install --editable=. wrong/version@user/channel'.format(reference), assert_error=True)
        self.assertIn("ERROR: Name and version from reference (wrong/version@user/channel) and "
                      "target conanfile.py (lib/version) must match", t.out)


class RemoveEditablePackageTest(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class APck(ConanFile):
            pass
        """)

    def test_remove_editable(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile,
                      CONAN_PACKAGE_LAYOUT_FILE: "", })
        t.run('export  . {}'.format(reference))  # No need to export, will create it on the fly
        t.run('install --editable=. {}'.format(reference))
        self.assertTrue(t.client_cache.installed_as_editable(reference))

        # Now remove editable
