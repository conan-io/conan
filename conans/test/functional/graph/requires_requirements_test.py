# coding=utf-8

import six
from parameterized import parameterized

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_INCACHE
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class SelfLoopTestCase(GraphManagerTest):

    @parameterized.expand([(False, ), (True, )])
    def test_requires(self, use_requirement_method):
        base1_ref = ConanFileReference.loads("base/1.0@user/testing")
        basea_ref = ConanFileReference.loads("base/aaa@user/testing")
        self._cache_recipe(base1_ref, GenConanfile())

        if not use_requirement_method:
            conanfile = str(GenConanfile().with_require(base1_ref))
            self.assertNotIn("def requirements", conanfile)
        else:
            conanfile = str(GenConanfile().with_requirement(base1_ref))
            self.assertNotIn("requires =", conanfile)

        # Error message is different depending on how the requirements are specified
        emsg_requires = "Loop detected: 'base/aaa@user/testing' requires 'base/aaa@user/testing'"
        emsg_requirements = "Duplicated requirement base/aaa@user/testing != base/1.0@user/testing"
        emsg = emsg_requirements if use_requirement_method else emsg_requires

        with six.assertRaisesRegex(self, ConanException, emsg):
            self.build_graph(conanfile, ref=basea_ref, create_ref=basea_ref)

        self.assertEqual(emsg_requires, emsg_requirements) # FIXME: Both messages should be the same
