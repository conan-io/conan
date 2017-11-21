import unittest

from conans.client.cmd.test import PackageTester
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement


class PackageTesterTest(unittest.TestCase):

    def unit_test_get_reference_to_test(self):

        obj = PackageTester(None, None)

        # No requires in the test_package/conanfile.py, specified parameters
        requires = {}
        ref = obj._get_reference_to_test(requires, "lib", "1.0", "user", "channel")
        self.assertEquals(ref, ConanFileReference.loads("lib/1.0@user/channel"))

        # One require, with same info that we are passing
        requires = {"lib": Requirement(ConanFileReference.loads("lib/1.0@user/channel"))}
        ref = obj._get_reference_to_test(requires, "lib", "1.0", "user", "channel")
        self.assertEquals(ref, ConanFileReference.loads("lib/1.0@user/channel"))

        # One require, with same info (Except user and channel)
        requires = {"lib": Requirement(ConanFileReference.loads("lib/1.0@user2/channel2"))}
        ref = obj._get_reference_to_test(requires, "lib", "1.0", "user", "channel")
        self.assertEquals(ref, ConanFileReference.loads("lib/1.0@user/channel"))

        # One require, for a different library
        requires = {"lib2": Requirement(ConanFileReference.loads("lib2/1.0@user2/channel2"))}
        ref = obj._get_reference_to_test(requires, "lib", "1.0", "user", "channel")
        self.assertEquals(ref, ConanFileReference.loads("lib/1.0@user/channel"))

        # Two requires, for different libraries
        requires = {"lib2": Requirement(ConanFileReference.loads("lib2/1.0@user2/channel2")),
                    "lib2": Requirement(ConanFileReference.loads("lib2/1.0@user2/channel2"))}
        ref = obj._get_reference_to_test(requires, "lib", "1.0", "user", "channel")
        self.assertEquals(ref, ConanFileReference.loads("lib/1.0@user/channel"))

        # Two requires, one matching
        requires = {"lib2": Requirement(ConanFileReference.loads("lib2/1.0@user2/channel2")),
                    "lib": Requirement(ConanFileReference.loads("lib/1.0@user2/channel2"))}
        ref = obj._get_reference_to_test(requires, "lib", "1.0", "user", "channel")
        self.assertEquals(ref, ConanFileReference.loads("lib/1.0@user/channel"))

        # Two requires, one matching, no specifing user/channel
        requires = {"lib2": Requirement(ConanFileReference.loads("lib2/1.0@user2/channel2")),
                    "lib": Requirement(ConanFileReference.loads("lib/1.0@user2/channel2"))}
        ref = obj._get_reference_to_test(requires, "lib", "1.0", None, None)
        self.assertEquals(ref, ConanFileReference.loads("lib/1.0@user2/channel2"))

        # Two requires, one matching, no specifing lib
        requires = {"lib2": Requirement(ConanFileReference.loads("lib2/1.0@user2/channel2")),
                    "lib": Requirement(ConanFileReference.loads("lib/1.0@user2/channel2"))}
        with self.assertRaisesRegexp(ConanException, "Cannot deduce the reference to be tested"):
            obj._get_reference_to_test(requires, None, None, None, None)

        # Library missmatching version
        requires = {"lib2": Requirement(ConanFileReference.loads("lib2/1.0@user2/channel2")),
                    "lib": Requirement(ConanFileReference.loads("lib/1.0@user2/channel2"))}
        with self.assertRaisesRegexp(ConanException, "he specified version doesn't match"):
            obj._get_reference_to_test(requires, "lib", "1.2", None, None)

