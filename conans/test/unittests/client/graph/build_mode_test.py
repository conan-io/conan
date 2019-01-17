import unittest

from conans.client.graph.build_mode import BuildMode
from conans.model.ref import ConanFileReference
from conans.errors import ConanException

from conans.test.utils.tools import TestBufferConanOutput
from conans.test.utils.conanfile import MockConanfile


class BuildModeTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.conanfile = MockConanfile(None)

    def test_valid_params(self):
        build_mode = BuildMode(["outdated", "missing"], self.output)
        self.assertTrue(build_mode.outdated)
        self.assertTrue(build_mode.missing)
        self.assertFalse(build_mode.never)

        build_mode = BuildMode(["never"], self.output)
        self.assertFalse(build_mode.outdated)
        self.assertFalse(build_mode.missing)
        self.assertTrue(build_mode.never)

    def test_invalid_configuration(self):
        with self.assertRaisesRegexp(ConanException,
                                     "--build=never not compatible with other options"):
            BuildMode(["outdated", "missing", "never"], self.output)

    def test_common_build_force(self):
        reference = ConanFileReference.loads("Hello/0.1@user/testing")
        build_mode = BuildMode(["Hello"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertEqual("", self.output)

    def test_non_matching_build_force(self):
        reference = ConanFileReference.loads("Bar/0.1@user/testing")
        build_mode = BuildMode(["Hello"], self.output)
        self.assertFalse(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertIn("ERROR: No package matching 'Hello' pattern", self.output)

    def test_full_reference_build_force(self):
        reference = ConanFileReference.loads("Bar/0.1@user/testing")
        build_mode = BuildMode(["Bar/0.1@user/testing"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertEqual("", self.output)

    def test_non_matching_full_reference_build_force(self):
        reference = ConanFileReference.loads("Bar/0.1@user/stable")
        build_mode = BuildMode(["Bar/0.1@user/testing"], self.output)
        self.assertFalse(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertIn("No package matching 'Bar/0.1@user/testing' pattern", self.output)

    def test_multiple_builds(self):
        reference = ConanFileReference.loads("Bar/0.1@user/stable")
        build_mode = BuildMode(["Bar", "Foo"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertIn("ERROR: No package matching", self.output)

    def test_allowed(self):
        build_mode = BuildMode(["outdated", "missing"], self.output)
        self.assertTrue(build_mode.allowed(self.conanfile))

        build_mode = BuildMode([], self.output)
        self.assertFalse(build_mode.allowed(self.conanfile))
