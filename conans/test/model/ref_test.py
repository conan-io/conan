import unittest
from conans.model.ref import ConanFileReference, PackageReference
from conans.errors import ConanException


class RefTest(unittest.TestCase):
    def basic_test(self):
        ref = ConanFileReference.loads("opencv/2.4.10 @ lasote/testing")
        self.assertEqual(ref.name, "opencv")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "lasote")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(str(ref), "opencv/2.4.10@lasote/testing")

        ref = ConanFileReference.loads("opencv_lite/2.4.10@phil_lewis/testing")
        self.assertEqual(ref.name, "opencv_lite")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "phil_lewis")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(str(ref), "opencv_lite/2.4.10@phil_lewis/testing")

        ref = ConanFileReference.loads("opencv/2.4.10@3rd-party/testing")
        self.assertEqual(ref.name, "opencv")
        self.assertEqual(ref.version, "2.4.10")
        self.assertEqual(ref.user, "3rd-party")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(str(ref), "opencv/2.4.10@3rd-party/testing")

    def errors_test(self):
        self.assertRaises(ConanException, ConanFileReference.loads, "")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv/2.4.10 @ lasote")
        self.assertRaises(ConanException, ConanFileReference.loads, "opencv??/2.4.10@laso/testing")
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

    def revisions_test(self):
        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing#23")
        self.assertEqual(ref.channel, "testing")
        self.assertEqual(ref.revision, "23")

        ref = ConanFileReference("opencv", "2.3", "lasote", "testing", "34")
        self.assertEqual(ref.revision, "34")

        p_ref = PackageReference.loads("opencv/2.4.10@lasote/testing#23:123123123#989")
        self.assertEqual(p_ref.revision, "989")
        self.assertEqual(p_ref.conan.revision, "23")
