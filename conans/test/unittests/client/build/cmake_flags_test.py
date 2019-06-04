import unittest
import six

from collections import OrderedDict

from conans.client.build.cmake_flags import CMakeDefinitions


class CMakeDefinitionsTest(unittest.TestCase):

    def setUp(self):
        self.cmake_definitions = CMakeDefinitions([("DEFINE1", None),
                                                   ("DEFINE2", "real_value"),
                                                   ("DEFINE3", ""),
                                                   ("DEFINE4", False)])

    def wrong_init_test(self):
        with six.assertRaisesRegex(self, AssertionError, "Definitions argument needs to be list of "
                                                         "tuples or an OrderedDict to preserve the "
                                                         "order of items"):
            CMakeDefinitions(["1", "2", "3"]).result()

    def not_ordered_dict_init_test(self):
        with six.assertRaisesRegex(self, AssertionError, "Definitions argument needs to be list of "
                                                         "tuples or an OrderedDict to preserve the "
                                                         "order of items"):
            CMakeDefinitions({"1": 1, "2": 2, "3": 3})

    def set_key_test(self):
        """
        Set key with real value
        """
        self.assertNotIn("DEFINE1", self.cmake_definitions.result().keys())
        self.cmake_definitions.set("DEFINE1", "value")
        self.assertEqual("value", self.cmake_definitions.result()["DEFINE1"])

    def set_key_another_value_test(self):
        """
        Setting another value to a key is not allowed. Assignment of value can only be done once
        """
        self.assertEqual("real_value", self.cmake_definitions.result()["DEFINE2"])
        with six.assertRaisesRegex(self, AssertionError,
                                   "Key 'DEFINE2' already has a value assigned: 'real_value'"):
            self.cmake_definitions.set("DEFINE2", "value")

    def set_new_key_test(self):
        """
        New keys are not allowed unless they are previously set
        """
        with six.assertRaisesRegex(self, AssertionError,
                                   "Key 'DEFINE5' not previously set in dictionary"):
            self.cmake_definitions.set("DEFINE5", "value")

    def get_result_test(self):
        """
        Check the expected result discarding definitions with None value
        """
        expected = OrderedDict([("DEFINE2", "real_value"),
                                ("DEFINE3", ""),
                                ("DEFINE4", False)])
        self.assertEqual(expected, self.cmake_definitions.result())

    def get_key_test(self):
        """
        Check getting a defined key is available but fails if it not defined
        """
        self.assertIsNone(self.cmake_definitions.get("DEFINE1"))
        self.assertEqual("real_value", self.cmake_definitions.get("DEFINE2"))
        self.assertEqual("", self.cmake_definitions.get("DEFINE3"))
        self.assertFalse(self.cmake_definitions.get("DEFINE4"))
        with six.assertRaisesRegex(self, AssertionError,
                                   "Key 'DEFINE5' not previously set in dictionary"):
            self.cmake_definitions.get("DEFINE5")

    def update_test(self):
        """
        Check dictionary is updated with new keys and values
        """
        previous_values = {"NEW_DEFINE": "NEW_CONTENT"}
        self.cmake_definitions.update(previous_values)
        self.assertEqual("NEW_CONTENT", self.cmake_definitions.result()["NEW_DEFINE"])

    def update_wrong_test(self):
        """
        Check dictionary is not updated with repeated keys
        """
        previous_values = {"DEFINE1": "NEW_CONTENT"}
        with six.assertRaisesRegex(self, AssertionError,
                                   "Key 'DEFINE1' previously set in dictionary"):
            self.cmake_definitions.update(previous_values)
        self.assertNotIn("DEFINE1", self.cmake_definitions.result().keys())
