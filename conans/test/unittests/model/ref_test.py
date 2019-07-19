import unittest

import six

from conans.errors import ConanException
from conans.model.ref import ConanFileReference, ConanName, InvalidNameException, PackageReference, \
    check_valid_ref, get_reference_fields


class RefTest(unittest.TestCase):
    def basic_test(self):
        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing")
        self.assertEqual(ref.name, "opencv")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "lasote")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, None)
        self.assertEqual(str(ref), "opencv/2.4.10@lasote/testing")

        ref = ConanFileReference.loads("opencv_lite/2.4.10@phil_lewis/testing")
        self.assertEqual(ref.name, "opencv_lite")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "phil_lewis")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, None)
        self.assertEqual(str(ref), "opencv_lite/2.4.10@phil_lewis/testing")

        ref = ConanFileReference.loads("opencv/2.4.10@3rd-party/testing")
        self.assertEqual(ref.name, "opencv")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "3rd-party")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, None)
        self.assertEqual(str(ref), "opencv/2.4.10@3rd-party/testing")

        ref = ConanFileReference.loads("opencv/2.4.10@3rd-party/testing#rev1")
        self.assertEqual(ref.revision, "rev1")

    def errors_test(self):
        self.assertRaises(ConanException, ConanFileReference.loads, "")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10")
        self.assertIsNone(ConanFileReference.loads("opencv/2.4.10@", validate=False).channel)
        self.assertIsNone(ConanFileReference.loads("opencv/2.4.10@", validate=False).user)
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10@lasote")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv??/2.4.10@laso/testing")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10 @ laso/testing")
        self.assertRaises(ConanException, ConanFileReference.loads, "o/2.4.10@laso/testing")
        self.assertRaises(ConanException, ConanFileReference.loads, ".opencv/2.4.10@lasote/testing")
        self.assertRaises(ConanException, ConanFileReference.loads, "o/2.4.10 @ lasote/testing")
        self.assertRaises(ConanException, ConanFileReference.loads, "lib/1.0@user&surname/channel")
        self.assertRaises(ConanException, ConanFileReference.loads,
                          "opencv%s/2.4.10@laso/testing" % "A" * 40)
        self.assertRaises(ConanException, ConanFileReference.loads,
                          "opencv/2.4.10%s@laso/testing" % "A" * 40)
        self.assertRaises(ConanException, ConanFileReference.loads,
                          "opencv/2.4.10@laso%s/testing" % "A" * 40)
        self.assertRaises(ConanException, ConanFileReference.loads,
                          "opencv/2.4.10@laso/testing%s" % "A" * 40)

        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10/laso/testing")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10/laso/test#1")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv@2.4.10/laso/test")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10/laso@test")

    def revisions_test(self):
        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing#23")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, "23")

        ref = ConanFileReference("opencv", "2.3", "lasote", "testing", "34")
        self.assertEqual(ref.revision, "34")

        pref = PackageReference.loads("opencv/2.4.10@lasote/testing#23:123123123#989")
        self.assertEqual(pref.revision, "989")
        self.assertEqual(pref.ref.revision, "23")

        pref = PackageReference(ref, "123123123#989")
        self.assertEqual(pref.ref.revision, "34")

    def equal_test(self):
        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing#23")
        ref2 = ConanFileReference.loads("opencv/2.4.10@lasote/testing#232")
        self.assertFalse(ref == ref2)
        self.assertTrue(ref != ref2)

        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing")
        ref2 = ConanFileReference.loads("opencv/2.4.10@lasote/testing#232")

        self.assertFalse(ref == ref2)
        self.assertTrue(ref != ref2)
        self.assertTrue(ref2 != ref)

        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing")
        ref2 = ConanFileReference.loads("opencv/2.4.10@lasote/testing")

        self.assertTrue(ref == ref2)
        self.assertFalse(ref != ref2)

        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing#23")
        ref2 = ConanFileReference.loads("opencv/2.4.10@lasote/testing#23")
        self.assertTrue(ref == ref2)
        self.assertFalse(ref != ref2)


class ConanNameTestCase(unittest.TestCase):

    def _check_invalid_format(self, value, *args):
        with six.assertRaisesRegex(self, InvalidNameException, "Valid names"):
            ConanName.validate_name(value, *args)

    def _check_invalid_type(self, value):
        with six.assertRaisesRegex(self, InvalidNameException, "is not a string"):
            ConanName.validate_name(value)

    def validate_name_test(self):
        self.assertIsNone(ConanName.validate_name("string.dot.under-score.123"))
        self.assertIsNone(ConanName.validate_name("_underscore+123"))
        self.assertIsNone(ConanName.validate_name("*"))
        self.assertIsNone(ConanName.validate_name("a" * ConanName._min_chars))
        self.assertIsNone(ConanName.validate_name("a" * ConanName._max_chars))
        self.assertIsNone(ConanName.validate_name("a" * 50))  # Regression test

    def validate_name_test_invalid_format(self):
        self._check_invalid_format("-no.dash.start")
        self._check_invalid_format("a" * (ConanName._min_chars - 1))
        self._check_invalid_format("a" * (ConanName._max_chars + 1))

    def validate_name_test_invalid_type(self):
        self._check_invalid_type(123.34)
        self._check_invalid_type(("item1", "item2",))

    def validate_name_version_test(self):
        self.assertIsNone(ConanName.validate_name("[vvvv]", version=True))

    def validate_name_version_test_invalid(self):
        self._check_invalid_format("[no.close.bracket", True)
        self._check_invalid_format("no.open.bracket]", True)


class CheckValidRefTest(unittest.TestCase):

    def test_string(self):
        self.assertTrue(check_valid_ref("package/1.0@user/channel", allow_pattern=False))
        self.assertTrue(check_valid_ref("package/1.0@user/channel", allow_pattern=True))

        self.assertFalse(check_valid_ref("package/*@user/channel", allow_pattern=False))
        self.assertTrue(check_valid_ref("package/1.0@user/channel", allow_pattern=True))

    def test_conanfileref(self):
        ref = ConanFileReference.loads("package/1.0@user/channel")
        self.assertTrue(check_valid_ref(ref, allow_pattern=False))
        self.assertTrue(check_valid_ref(ref, allow_pattern=True))

        ref_pattern = ConanFileReference.loads("package/*@user/channel")
        self.assertFalse(check_valid_ref(ref_pattern, allow_pattern=False))
        self.assertTrue(check_valid_ref(ref_pattern, allow_pattern=True))

    def test_incomplete_refs(self):
        self.assertFalse(check_valid_ref("package/1.0", allow_pattern=False))
        self.assertFalse(check_valid_ref("package/1.0@user", allow_pattern=False))
        self.assertFalse(check_valid_ref("package/1.0@/channel", allow_pattern=False))
        self.assertFalse(check_valid_ref("lib@#rev", allow_pattern=False))


class GetReferenceFieldsTest(unittest.TestCase):

    def test_fields_complete(self):

        # No matter if we say we allow partial references for "user/channel", if we
        # provide this patterns everything is parsed correctly
        for user_channel_input in [True, False]:
            tmp = get_reference_fields("lib/1.0@user", user_channel_input=user_channel_input)
            self.assertEqual(tmp, ("lib", "1.0", "user", None, None))

            tmp = get_reference_fields("lib/1.0@/channel", user_channel_input=user_channel_input)
            self.assertEqual(tmp, ("lib", "1.0", None, "channel", None))

            # FIXME: 2.0 in this case lib is considered the version, weird.
            tmp = get_reference_fields("lib@#rev", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, "lib", None, None, "rev"))

            # FIXME: 2.0 in this case lib is considered the version, weird.
            tmp = get_reference_fields("lib@/channel#rev", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, "lib", None, "channel", "rev"))

            tmp = get_reference_fields("/1.0@user/#rev", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, "1.0", "user", None, "rev"))

            tmp = get_reference_fields("/@/#", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, None, None, None, None))

            tmp = get_reference_fields("lib/1.0@/", user_channel_input=user_channel_input)
            self.assertEqual(tmp, ("lib", "1.0", None, None, None))

            tmp = get_reference_fields("lib/1.0@", user_channel_input=user_channel_input)
            self.assertEqual(tmp, ("lib", "1.0", None, None, None))

            tmp = get_reference_fields("lib/@", user_channel_input=user_channel_input)
            self.assertEqual(tmp, ("lib", None, None, None, None))

            tmp = get_reference_fields("/@", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, None, None, None, None))

            tmp = get_reference_fields("@", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, None, None, None, None))

            tmp = get_reference_fields("lib/1.0@user/channel#rev",
                                       user_channel_input=user_channel_input)
            self.assertEqual(tmp, ("lib", "1.0", "user", "channel", "rev"))

            # FIXME: 2.0 in this case lib is considered the version, weird.
            tmp = get_reference_fields("lib@user/channel", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, "lib", "user", "channel", None))

            tmp = get_reference_fields("/@/#", user_channel_input=user_channel_input)
            self.assertEqual(tmp, (None, None, None, None, None))

    def test_only_user_channel(self):
        tmp = get_reference_fields("user/channel", user_channel_input=True)
        self.assertEqual(tmp, (None, None, "user", "channel", None))

        tmp = get_reference_fields("user", user_channel_input=True)
        self.assertEqual(tmp, (None, None, "user", None, None))

        tmp = get_reference_fields("/channel", user_channel_input=True)
        self.assertEqual(tmp, (None, None, None, "channel", None))
