# coding=utf-8

import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_editable_layout import CONAN_PACKAGE_LAYOUT_FILE
from conans.test.utils.tools import TestClient, TestServer


class EmptyCacheTestMixin(object):

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

    def setUp(self):
        self.servers = {"default": TestServer()}
        self.t = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]},
                            path_with_spaces=False)
        self.reference = ConanFileReference.loads('lib/version@user/channel')
        self.assertFalse(os.path.exists(self.t.client_cache.conan(self.reference)))

    def tearDown(self):
        self.t.run('link {} --remove'.format(self.reference))
        self.assertFalse(self.t.client_cache.installed_as_editable(self.reference))
        self.assertFalse(os.listdir(self.t.client_cache.conan(self.reference)))


class CreateLinkOverEmptyCache(EmptyCacheTestMixin, unittest.TestCase):

    def test_do_nothing(self):
        self.t.save(files={'conanfile.py': self.conanfile,
                           CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        self.t.run('link . {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

    def test_install_requirements(self):
        # Create a parent and remove it from cache
        ref_parent = ConanFileReference.loads("parent/version@lasote/channel")
        self.t.save(files={'conanfile.py': self.conanfile})
        self.t.run('create . {}'.format(ref_parent))
        self.t.run('upload {} --all'.format(ref_parent))
        self.t.run('remove {} --force'.format(ref_parent))
        self.assertFalse(os.path.exists(self.t.client_cache.conan(ref_parent)))

        # Create our project and link it
        self.t.save(files={'conanfile.py':
                              self.conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                           CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        self.t.run('link . {}'.format(self.reference))

        # Install our project and check that everything is in place
        self.t.run('install {}'.format(self.reference))
        self.assertIn("    lib/version@user/channel from local cache - Editable", self.t.out)
        self.assertIn("    parent/version@lasote/channel from 'default' - Downloaded", self.t.out)
        self.assertTrue(os.path.exists(self.t.client_cache.conan(ref_parent)))

    def test_middle_graph(self):
        # Create a parent and remove it from cache
        ref_parent = ConanFileReference.loads("parent/version@lasote/channel")
        self.t.save(files={'conanfile.py': self.conanfile})
        self.t.run('create . {}'.format(ref_parent))
        self.t.run('upload {} --all'.format(ref_parent))
        self.t.run('remove {} --force'.format(ref_parent))
        self.assertFalse(os.path.exists(self.t.client_cache.conan(ref_parent)))

        # Create our project and link it
        path_to_lib = os.path.join(self.t.current_folder, 'lib')
        self.t.save(files={'conanfile.py':
                               self.conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                           CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, },
                    path=path_to_lib)
        self.t.run('link {} {}'.format(path_to_lib, self.reference))

        # Create a child an install it (in other folder, do not override the link!)
        path_to_child = os.path.join(self.t.current_folder, 'child')
        ref_child = ConanFileReference.loads("child/version@lasote/channel")
        self.t.save(files={'conanfile.py': self.conanfile_base.
                    format(body='requires = "{}"'.format(self.reference)), },
                    path=path_to_child)
        self.t.run("create {} {}".format(path_to_child, ref_child))
        self.assertIn("    child/version@lasote/channel from local cache - Cache", self.t.out)
        self.assertIn("    lib/version@user/channel from local cache - Editable", self.t.out)
        self.assertIn("    parent/version@lasote/channel from 'default' - Downloaded", self.t.out)
        self.assertTrue(os.path.exists(self.t.client_cache.conan(ref_parent)))



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


    def test_link_existing_cache(self):
        pass

    def test_install_without_deps(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile,
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        #t.run('export  . {}'.format(reference))
        t.run('link . {}'.format(reference))

        self.assertIn("Reference 'lib/version@user/name' linked to directory", t.out)
        self.assertTrue(t.client_cache.installed_as_editable(reference))
        layout = t.client_cache.package_layout(reference)
        self.assertTrue(layout.installed_as_editable())
        self.assertEqual(layout.conan(), t.current_folder)

    def test_install_with_deps(self):
        ref_parent = ConanFileReference.loads("parent/version@user/name")
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        #t.save(files={'conanfile.py': self.conanfile})
        #t.run('create . {}'.format(ref_parent))

        t.save(files={'conanfile.py':
                          self.conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        #t.run('export . {}'.format(reference))
        t.run('link . {}'.format(reference))

        self.assertIn("Reference 'lib/version@user/name' linked to directory", t.out)
        self.assertTrue(t.client_cache.installed_as_editable(reference))
        layout = t.client_cache.package_layout(reference)
        self.assertTrue(layout.installed_as_editable())
        self.assertEqual(layout.conan(), t.current_folder)

    def test_install_with_deps_non_local(self):
        ref_parent = ConanFileReference.loads("parent/version@lasote/name")
        reference = ConanFileReference.loads('lib/version@lasote/name')

        servers = {"default": TestServer()}
        t1 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        t2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        #t1.save(files={'conanfile.py': self.conanfile})
        #t1.run('create . {}'.format(ref_parent))
        #t1.run('upload {}'.format(ref_parent))

        t2.save(files={'conanfile.py':
                           self.conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                       CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        #t2.run('export . {}'.format(reference))
        t2.run('link . {}'.format(reference))

        self.assertIn("Reference 'lib/version@lasote/name' linked to directory", t2.out)
        self.assertTrue(t2.client_cache.installed_as_editable(reference))
        layout = t2.client_cache.package_layout(reference)
        self.assertTrue(layout.installed_as_editable())
        self.assertEqual(layout.conan(), t2.current_folder)

    def test_install_without_package_layout_file(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={os.path.join('conanfile.py'): self.conanfile})
        #t.run('export  . {}'.format(reference))
        t.run('link . {}'.format(reference), assert_error=True)

        self.assertFalse(os.path.exists(CONAN_PACKAGE_LAYOUT_FILE))
        self.assertIn("ERROR: In order to link a package in editable mode, it is required a", t.out)

    """
    def test_install_failed_export_first(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile,
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        t.run('link . {}'.format(reference), assert_error=True)
        self.assertIn("ERROR: In order to link a package in editable mode, "
                      "its recipe must be already exported to the cache", t.out)
        self.assertFalse(t.client_cache.installed_as_editable(reference))  # Remove editable
    """

    """
    def test_install_failed_deps(self):
        reference = ConanFileReference.loads('lib/version@user/name')

        t = TestClient()
        t.save(files={'conanfile.py': self.conanfile_base.format(body='requires = "aa/bb@cc/dd"'),
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        t.run('export  . {}'.format(reference))
        t.run('link . {}'.format(reference), assert_error=True)

        self.assertIn("ERROR: Failed requirement 'aa/bb@cc/dd'", t.out)
        self.assertFalse(t.client_cache.installed_as_editable(reference))  # Remove editable
    """

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
        t.run('link . wrong/version@user/channel', assert_error=True)
        self.assertIn("ERROR: Name and version from reference (wrong/version@user/channel) and "
                      "target conanfile.py (lib/version) must match", t.out)
