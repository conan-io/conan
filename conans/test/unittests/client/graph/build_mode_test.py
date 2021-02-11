import unittest

import six

from conans.client.graph.build_mode import BuildMode
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.utils.mocks import MockConanfile, TestBufferConanOutput


class BuildModeTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.conanfile = MockConanfile(None)

    def test_valid_params(self):
        build_mode = BuildMode(["outdated", "missing"], self.output)
        self.assertTrue(build_mode.outdated)
        self.assertTrue(build_mode.missing)
        self.assertFalse(build_mode.never)
        self.assertFalse(build_mode.cascade)

        build_mode = BuildMode(["never"], self.output)
        self.assertFalse(build_mode.outdated)
        self.assertFalse(build_mode.missing)
        self.assertTrue(build_mode.never)
        self.assertFalse(build_mode.cascade)

        build_mode = BuildMode(["cascade"], self.output)
        self.assertFalse(build_mode.outdated)
        self.assertFalse(build_mode.missing)
        self.assertFalse(build_mode.never)
        self.assertTrue(build_mode.cascade)

    def test_invalid_configuration(self):
        for mode in ["outdated", "missing", "cascade"]:
            with six.assertRaisesRegex(self, ConanException,
                                       "--build=never not compatible with other options"):
                BuildMode([mode, "never"], self.output)

    def test_common_build_force(self):
        reference = ConanFileReference.loads("Hello/0.1@user/testing")
        build_mode = BuildMode(["Hello"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertEqual("", self.output)

    def test_no_user_channel(self):
        reference = ConanFileReference.loads("Hello/0.1@")
        build_mode = BuildMode(["Hello/0.1@"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertEqual("", self.output)

    def test_revision_included(self):
        reference = ConanFileReference.loads("Hello/0.1@user/channel#rrev1")
        build_mode = BuildMode(["Hello/0.1@user/channel#rrev1"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertEqual("", self.output)

    def test_no_user_channel_revision_included(self):
        reference = ConanFileReference.loads("Hello/0.1@#rrev1")
        build_mode = BuildMode(["Hello/0.1@#rrev1"], self.output)
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

    def test_casing(self):
        reference = ConanFileReference.loads("Boost/1.69.0@user/stable")

        build_mode = BuildMode(["Boost"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode = BuildMode(["Bo*"], self.output)
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertEqual("", self.output)

        build_mode = BuildMode(["boost"], self.output)
        self.assertFalse(build_mode.forced(self.conanfile, reference))
        build_mode = BuildMode(["bo*"], self.output)
        self.assertFalse(build_mode.forced(self.conanfile, reference))
        build_mode.report_matches()
        self.assertIn("ERROR: No package matching", self.output)

    def test_pattern_matching(self):
        build_mode = BuildMode(["Boost*"], self.output)
        reference = ConanFileReference.loads("Boost/1.69.0@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("Boost_Addons/1.0.0@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("MyBoost/1.0@user/stable")
        self.assertFalse(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("foo/Boost@user/stable")
        self.assertFalse(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("foo/1.0@Boost/stable")
        self.assertFalse(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("foo/1.0@user/Boost")
        self.assertFalse(build_mode.forced(self.conanfile, reference))

        build_mode = BuildMode(["foo/*@user/stable"], self.output)
        reference = ConanFileReference.loads("foo/1.0.0@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("foo/1.0@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("foo/1.0.0-abcdefg@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))

        build_mode = BuildMode(["*@user/stable"], self.output)
        reference = ConanFileReference.loads("foo/1.0.0@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("bar/1.0@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("foo/1.0.0-abcdefg@user/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("foo/1.0.0@NewUser/stable")
        self.assertFalse(build_mode.forced(self.conanfile, reference))

        build_mode = BuildMode(["*Tool"], self.output)
        reference = ConanFileReference.loads("Tool/0.1@lasote/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("PythonTool/0.1@lasote/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("SomeTool/1.2@user/channel")
        self.assertTrue(build_mode.forced(self.conanfile, reference))

        build_mode = BuildMode(["Tool/*"], self.output)
        reference = ConanFileReference.loads("Tool/0.1@lasote/stable")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("Tool/1.1@user/testing")
        self.assertTrue(build_mode.forced(self.conanfile, reference))
        reference = ConanFileReference.loads("PythonTool/0.1@lasote/stable")
        self.assertFalse(build_mode.forced(self.conanfile, reference))

        build_mode.report_matches()
        self.assertEqual("", self.output)
