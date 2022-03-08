# coding=utf-8

import os
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, TestServer


conanfile_base = textwrap.dedent("""\
    from conan import ConanFile

    class APck(ConanFile):
        {body}
    """)
conanfile = conanfile_base.format(body="pass")

conan_package_layout = textwrap.dedent("""\
    [includedirs]
    src/include
    """)


class EmptyCacheTestMixin(object):
    """ Will check that the cache after using the link is empty """
    def setUp(self):
        self.servers = {"default": TestServer()}
        self.t = TestClient(servers=self.servers,  inputs=["admin", "password"],
                            path_with_spaces=False)
        self.ref = RecipeReference.loads('lib/version@user/channel')
        self.assertFalse(os.path.exists(self.t.get_latest_ref_layout(self.ref).base_folder))

    def tearDown(self):
        self.t.run('editable remove {}'.format(self.ref))
        self.assertFalse(self.t.cache.installed_as_editable(self.ref))


class ExistingCacheTestMixin(object):
    """ Will check that the cache after using the link contains the same data as before """
    def setUp(self):
        self.servers = {"default": TestServer()}
        self.t = TestClient(servers=self.servers, inputs=["admin", "password"],
                            path_with_spaces=False)
        self.ref = RecipeReference.loads('lib/version@user/channel')
        self.t.save(files={'conanfile.py': conanfile})
        self.t.run('create . {}'.format(self.ref))
        self.assertTrue(os.path.exists(self.t.get_latest_ref_layout(self.ref).base_folder))
        self.assertListEqual(sorted(os.listdir(self.t.get_latest_ref_layout(self.ref).base_folder)),
                             ['build', 'export', 'export_source', 'locks', 'metadata.json',
                              'metadata.json.lock', 'package', 'source'])

    def tearDown(self):
        self.t.run('editable remove {}'.format(self.ref))
        self.assertTrue(os.path.exists(self.t.get_latest_ref_layout(self.ref).base_folder))
        self.assertListEqual(sorted(os.listdir(self.t.get_latest_ref_layout(self.ref).base_folder)),
                             ['build', 'export', 'export_source', 'locks', 'metadata.json',
                              'metadata.json.lock', 'package', 'source'])


class RelatedToGraphBehavior(object):

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_do_nothing(self):
        self.t.save(files={'conanfile.py': conanfile,
                           "mylayout": conan_package_layout, })
        self.t.run('editable add . {}'.format(self.ref))
        self.assertTrue(self.t.cache.installed_as_editable(self.ref))

    @parameterized.expand([(True, ), (False, )])
    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_install_requirements(self, update):
        # Create a parent and remove it from cache
        ref_parent = RecipeReference.loads("parent/version@lasote/channel")
        self.t.save(files={'conanfile.py': conanfile})
        self.t.run('create . {}'.format(ref_parent))
        self.t.run('upload {} -r default'.format(ref_parent))
        self.t.run('remove {} --force -r default'.format(ref_parent))
        self.assertFalse(os.path.exists(self.t.get_latest_ref_layout(ref_parent).base_folder))

        # Create our project and link it
        self.t.save(files={'conanfile.py':
                           conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                           "mylayout": conan_package_layout, })
        self.t.run('editable add . {}'.format(self.ref))

        # Install our project and check that everything is in place
        update = ' --update' if update else ''
        self.t.run('install --requires={}{}'.format(self.ref, update))
        self.assertIn("    lib/version@user/channel from user folder - Editable", self.t.out)
        self.assertIn("    parent/version@lasote/channel from 'default' - Downloaded",
                      self.t.out)
        self.assertTrue(os.path.exists(self.t.get_latest_ref_layout(ref_parent).base_folder()))

    @parameterized.expand([(True,), (False,)])
    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_middle_graph(self, update):
        # Create a parent and remove it from cache
        ref_parent = RecipeReference.loads("parent/version@lasote/channel")
        self.t.save(files={'conanfile.py': conanfile})
        self.t.run('create . {}'.format(ref_parent))
        self.t.run('upload {}'.format(ref_parent))
        self.t.run('remove {} --force'.format(ref_parent))
        self.assertFalse(os.path.exists(self.t.get_latest_ref_layout(ref_parent).base_folder()))

        # Create our project and link it
        path_to_lib = os.path.join(self.t.current_folder, 'lib')
        self.t.save(files={'conanfile.py':
                           conanfile_base.format(body='requires = "{}"'.format(ref_parent)),
                           "mylayout": conan_package_layout, },
                    path=path_to_lib)
        self.t.run('editable add "{}" {}'.format(path_to_lib, self.ref))

        # Create a child an install it (in other folder, do not override the link!)
        path_to_child = os.path.join(self.t.current_folder, 'child')
        ref_child = RecipeReference.loads("child/version@lasote/channel")
        self.t.save(files={'conanfile.py': conanfile_base.
                    format(body='requires = "{}"'.format(self.ref)), },
                    path=path_to_child)

        update = ' --update' if update else ''
        self.t.run('create "{}" {} {}'.format(path_to_child, ref_child, update))
        child_remote = 'No remote' if update else 'Cache'
        self.assertIn("    child/version@lasote/channel from local cache - {}".format(child_remote),
                      self.t.out)
        self.assertIn("    lib/version@user/channel from user folder - Editable", self.t.out)
        self.assertIn("    parent/version@lasote/channel from 'default' - Downloaded", self.t.out)
        self.assertTrue(os.path.exists(self.t.get_latest_ref_layout(ref_parent).base_folder()))


class CreateLinkOverEmptyCache(EmptyCacheTestMixin, RelatedToGraphBehavior, unittest.TestCase):
    pass


class CreateLinkOverExistingCache(ExistingCacheTestMixin, RelatedToGraphBehavior, unittest.TestCase):
    pass
