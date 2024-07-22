import unittest
from collections import OrderedDict

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestServer, TurboTestClient, GenConanfile


class InstallCascadeTest(unittest.TestCase):

    def setUp(self):
        """
         A
        / \
       B   C
       |    \
       D    |
      / \   |
      |  \ /
      E   F
        """
        server = TestServer()
        servers = OrderedDict([("default", server)])
        self.client = TurboTestClient(servers=servers)

        self.ref_a = RecipeReference.loads("liba/1.0@conan/stable")
        self.client.create(self.ref_a, conanfile=GenConanfile())

        self.ref_b = RecipeReference.loads("libb/1.0@conan/stable")
        self.client.create(self.ref_b, conanfile=GenConanfile().with_requirement(self.ref_a))

        self.ref_c = RecipeReference.loads("libc/1.0@conan/stable")
        self.client.create(self.ref_c, conanfile=GenConanfile().with_requirement(self.ref_a))

        self.ref_d = RecipeReference.loads("libd/1.0@conan/stable")
        self.client.create(self.ref_d, conanfile=GenConanfile().with_requirement(self.ref_b))

        self.ref_e = RecipeReference.loads("libe/1.0@conan/stable")
        self.client.create(self.ref_e, conanfile=GenConanfile().with_requirement(self.ref_d))

        self.ref_f = RecipeReference.loads("libf/1.0@conan/stable")
        conanfile = GenConanfile().with_requirement(self.ref_c).with_requirement(self.ref_d)
        self.client.create(self.ref_f, conanfile=conanfile)

    def _assert_built(self, refs):
        for ref in refs:
            self.assertIn("{}: Copying sources to build folder".format(ref), self.client.out)
        for ref in [self.ref_a, self.ref_b, self.ref_c, self.ref_d, self.ref_e, self.ref_f]:
            if ref not in refs:
                self.assertNotIn("{}: Copying sources to build folder".format(ref),
                                 self.client.out)

    def test_install_cascade_only_affected(self):
        project = RecipeReference.loads("project/1.0@conan/stable")
        project_cf = GenConanfile().with_requirement(self.ref_e).with_requirement(self.ref_f)

        # Building A everything is built
        self.client.create(project, conanfile=project_cf,
                           args="--build {} --build cascade".format(self.ref_a))
        self._assert_built([self.ref_a, self.ref_b, self.ref_c, self.ref_d,
                            self.ref_e, self.ref_f, project])

        # Building D builds E, F and project
        self.client.create(project, conanfile=project_cf,
                           args="--build {} --build cascade".format(self.ref_d))
        self._assert_built([self.ref_d, self.ref_e, self.ref_f, project])

        # Building E only builds E and project
        self.client.create(project, conanfile=project_cf,
                           args="--build {} --build cascade".format(self.ref_e))
        self._assert_built([self.ref_e, project])

        # Building project only builds project
        self.client.create(project, conanfile=project_cf,
                           args="--build {} --build cascade".format(project))
        self._assert_built([project])

        # Building C => builds F and project
        self.client.create(project, conanfile=project_cf,
                           args="--build {} --build cascade".format(self.ref_c))
        self._assert_built([project, self.ref_f, self.ref_c])
