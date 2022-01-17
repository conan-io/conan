import unittest

import pytest

from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.model.ref import ConanName, InvalidNameException, \
    check_valid_ref, get_reference_fields


class RefTest(unittest.TestCase):
    def test_basic(self):
        ref = RecipeReference.loads("opencv/2.4.10@lasote/testing")
        self.assertEqual(ref.name, "opencv")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "lasote")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, None)
        self.assertEqual(str(ref), "opencv/2.4.10@lasote/testing")

        ref = RecipeReference.loads("opencv_lite/2.4.10@phil_lewis/testing")
        self.assertEqual(ref.name, "opencv_lite")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "phil_lewis")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, None)
        self.assertEqual(str(ref), "opencv_lite/2.4.10@phil_lewis/testing")

        ref = RecipeReference.loads("opencv/2.4.10@3rd-party/testing")
        self.assertEqual(ref.name, "opencv")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "3rd-party")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, None)
        self.assertEqual(str(ref), "opencv/2.4.10@3rd-party/testing")

        ref = RecipeReference.loads("opencv/2.4.10@3rd-party/testing#rev1")
        self.assertEqual(ref.revision, "rev1")

    @pytest.mark.xfail(reason="The validation of the references shouldn't be done in the model "
                              "anymore")
    def test_errors(self):
        self.assertRaises(ConanException, RecipeReference.loads, "")
        self.assertIsNone(RecipeReference.loads("opencv/2.4.10@", validate=False).channel)
        self.assertIsNone(RecipeReference.loads("opencv/2.4.10@", validate=False).user)
        self.assertRaises(ConanException, RecipeReference.loads, "opencv/2.4.10@lasote")
        self.assertRaises(ConanException, RecipeReference.loads, "opencv??/2.4.10@laso/testing")
        self.assertRaises(ConanException, RecipeReference.loads, "opencv/2.4.10 @ laso/testing")
        self.assertRaises(ConanException, RecipeReference.loads, "o/2.4.10@laso/testing")
        self.assertRaises(ConanException, RecipeReference.loads, ".opencv/2.4.10@lasote/testing")
        self.assertRaises(ConanException, RecipeReference.loads, "o/2.4.10 @ lasote/testing")
        self.assertRaises(ConanException, RecipeReference.loads, "lib/1.0@user&surname/channel")
        self.assertRaises(ConanException, RecipeReference.loads,
                          "opencv%s/2.4.10@laso/testing" % "A" * 40)
        self.assertRaises(ConanException, RecipeReference.loads,
                          "opencv/2.4.10%s@laso/testing" % "A" * 40)
        self.assertRaises(ConanException, RecipeReference.loads,
                          "opencv/2.4.10@laso%s/testing" % "A" * 40)
        self.assertRaises(ConanException, RecipeReference.loads,
                          "opencv/2.4.10@laso/testing%s" % "A" * 40)

        self.assertRaises(ConanException, RecipeReference.loads, "opencv/2.4.10/laso/testing")
        self.assertRaises(ConanException, RecipeReference.loads, "opencv/2.4.10/laso/test#1")
        self.assertRaises(ConanException, RecipeReference.loads, "opencv@2.4.10/laso/test")
        self.assertRaises(ConanException, RecipeReference.loads, "opencv/2.4.10/laso@test")

    def test_revisions(self):
        ref = RecipeReference.loads("opencv/2.4.10@lasote/testing#23")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, "23")

        ref = RecipeReference.loads("opencv/2.4.10#23")
        self.assertIsNone(ref.channel)
        self.assertIsNone(ref.user)
        self.assertEqual(ref.name, "opencv")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.revision, "23")

        ref = RecipeReference("opencv", "2.3", "lasote", "testing", "34")
        self.assertEqual(ref.revision, "34")

        pref = PkgReference.loads("opencv/2.4.10@lasote/testing#23:123123123#989")
        self.assertEqual(pref.revision, "989")
        self.assertEqual(pref.ref.revision, "23")

        pref = PkgReference(ref, "123123123#989")
        self.assertEqual(pref.ref.revision, "34")

    def test_equal(self):
        ref = RecipeReference.loads("opencv/2.4.10@lasote/testing#23")
        ref2 = RecipeReference.loads("opencv/2.4.10@lasote/testing#232")
        self.assertFalse(ref == ref2)
        self.assertTrue(ref != ref2)

        ref = RecipeReference.loads("opencv/2.4.10@lasote/testing")
        ref2 = RecipeReference.loads("opencv/2.4.10@lasote/testing#232")

        self.assertFalse(ref == ref2)
        self.assertTrue(ref != ref2)
        self.assertTrue(ref2 != ref)

        ref = RecipeReference.loads("opencv/2.4.10@lasote/testing")
        ref2 = RecipeReference.loads("opencv/2.4.10@lasote/testing")

        self.assertTrue(ref == ref2)
        self.assertFalse(ref != ref2)

        ref = RecipeReference.loads("opencv/2.4.10@lasote/testing#23")
        ref2 = RecipeReference.loads("opencv/2.4.10@lasote/testing#23")
        self.assertTrue(ref == ref2)
        self.assertFalse(ref != ref2)


class ConanNameTestCase(unittest.TestCase):

    def _check_invalid_format(self, value, *args):
        with self.assertRaisesRegex(InvalidNameException, "Valid names"):
            ConanName.validate_name(value, *args)

    def _check_invalid_version(self, name, version):
        with self.assertRaisesRegex(InvalidNameException, "invalid version number"):
            ConanName.validate_version(version, name)

    def _check_invalid_type(self, value):
        with self.assertRaisesRegex(InvalidNameException, "is not a string"):
            ConanName.validate_name(value)

    def test_validate_name(self):
        self.assertIsNone(ConanName.validate_name("string.dot.under-score.123"))
        self.assertIsNone(ConanName.validate_name("_underscore+123"))
        self.assertIsNone(ConanName.validate_name("*"))
        self.assertIsNone(ConanName.validate_name("a" * ConanName._min_chars))
        self.assertIsNone(ConanName.validate_name("a" * ConanName._max_chars))
        self.assertIsNone(ConanName.validate_name("a" * 50))  # Regression test

    def test_validate_name_invalid_format(self):
        self._check_invalid_format("-no.dash.start")
        self._check_invalid_format("a" * (ConanName._min_chars - 1))
        self._check_invalid_format("a" * (ConanName._max_chars + 1))

    def test_validate_name_invalid_type(self):
        self._check_invalid_type(123.34)
        self._check_invalid_type(("item1", "item2",))

    def test_validate_name_version(self):
        self.assertIsNone(ConanName.validate_version("name", "[vvvv]"))

    def test_validate_name_version_invalid(self):
        self._check_invalid_version("name", "[no.close.bracket")
        self._check_invalid_version("name", "no.open.bracket]")


class CheckValidRefTest(unittest.TestCase):

    def test_string(self):
        self.assertTrue(check_valid_ref("package/1.0@user/channel"))
        self.assertTrue(check_valid_ref("package/1.0@user/channel"))
        self.assertTrue(check_valid_ref("package/[*]@user/channel"))
        self.assertTrue(check_valid_ref("package/[>1.0]@user/channel"))
        self.assertTrue(check_valid_ref("package/[1.*]@user/channel"))

        # Patterns are invalid
        self.assertFalse(check_valid_ref("package/*@user/channel"))
        self.assertFalse(check_valid_ref("package/1.0@user/*"))
        self.assertFalse(check_valid_ref("package/1.0@user/chan*"))
        self.assertFalse(check_valid_ref("package/[>1.0]@user/chan*"))
        self.assertFalse(check_valid_ref("*/1.0@user/channel"))
        self.assertFalse(check_valid_ref("package*/1.0@user/channel"))

        # * pattern is valid in non stric_mode
        self.assertTrue(check_valid_ref("package/*@user/channel", strict_mode=False))
        self.assertTrue(check_valid_ref("package/*@user/*", strict_mode=False))

        # But other patterns are not valid in non stric_mode
        self.assertFalse(check_valid_ref("package/1.0@user/chan*", strict_mode=False))

    def test_incomplete_refs(self):
        self.assertTrue(check_valid_ref("package/1.0", strict_mode=False))
        self.assertFalse(check_valid_ref("package/1.0"))
        self.assertFalse(check_valid_ref("package/1.0@user"))
        self.assertFalse(check_valid_ref("package/1.0@/channel"))
        self.assertFalse(check_valid_ref("lib@#rev"))


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

        ref_pattern = RecipeReference.loads("package/*@user/channel")
        self.assertFalse(check_valid_ref(ref_pattern, strict_mode=False))

