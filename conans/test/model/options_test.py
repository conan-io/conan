import unittest
from conans.model.options import OptionsValues, PackageOptions, Options
from conans.model.ref import ConanFileReference
from conans.test.tools import TestBufferConanOutput
from conans.model.values import Values
from conans.errors import ConanException


class OptionsTest(unittest.TestCase):

    def setUp(self):
        package_options = PackageOptions.loads("""{static: [True, False],
        optimized: [2, 3, 4],
        path: ANY}""")
        package_options.values = Values.loads("static=True\noptimized=3\npath=NOTDEF")
        self.sut = Options(package_options)

    def items_test(self):
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "NOTDEF"),
                                            ("static", "True")])
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "NOTDEF"),
                                            ("static", "True")])

    def change_test(self):
        self.sut.path = "C:/MyPath"
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "C:/MyPath"),
                                            ("static", "True")])
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "C:/MyPath"),
                                            ("static", "True")])
        with self.assertRaisesRegexp(ConanException,
                                     "'5' is not a valid 'options.optimized' value"):
            self.sut.optimized = 5

    def boolean_test(self):
        self.sut.static = False
        self.assertFalse(self.sut.static)
        self.assertTrue(not self.sut.static)
        self.assertTrue(self.sut.static == False)
        self.assertFalse(self.sut.static == True)
        self.assertFalse(self.sut.static != False)
        self.assertTrue(self.sut.static != True)
        self.assertTrue(self.sut.static == "False")
        self.assertTrue(self.sut.static != "True")

    def basic_test(self):
        options = OptionsValues.loads("""other_option=True
        optimized_var=3
        Poco:deps_bundled=True
        Boost:static=False
        Boost:thread=True
        Boost:thread.multi=off
        Hello1:static=False
        Hello1:optimized=4
        """)
        down_ref = ConanFileReference.loads("Hello0/0.1@diego/testing")
        own_ref = ConanFileReference.loads("Hello1/0.1@diego/testing")
        output = TestBufferConanOutput()
        self.sut.propagate_upstream(options, down_ref, own_ref, output)
        self.assertEqual(self.sut.values.as_list(), [("optimized", "4"),
                                                     ("path", "NOTDEF"),
                                                     ("static", "False"),
                                                     ("Boost:static", "False"),
                                                     ("Boost:thread", "True"),
                                                     ("Boost:thread.multi", "off"),
                                                     ("Poco:deps_bundled", "True")])

        options2 = OptionsValues.loads("""other_option=True
        optimized_var=3
        Poco:deps_bundled=What
        Boost:static=2
        Boost:thread=Any
        Boost:thread.multi=on
        Hello1:static=True
        Hello1:optimized=2
        """)
        down_ref = ConanFileReference.loads("Hello2/0.1@diego/testing")
        self.sut.propagate_upstream(options2, down_ref, own_ref, output)
        self.assertIn("""WARN: Hello2/0.1@diego/testing tried to change Hello1/0.1@diego/testing option optimized to 2
but it was already assigned to 4 by Hello0/0.1@diego/testing
WARN: Hello2/0.1@diego/testing tried to change Hello1/0.1@diego/testing option static to True
but it was already assigned to False by Hello0/0.1@diego/testing
WARN: Hello2/0.1@diego/testing tried to change Hello1/0.1@diego/testing option Boost:static to 2
but it was already assigned to False by Hello0/0.1@diego/testing
WARN: Hello2/0.1@diego/testing tried to change Hello1/0.1@diego/testing option Boost:thread to Any
but it was already assigned to True by Hello0/0.1@diego/testing
WARN: Hello2/0.1@diego/testing tried to change Hello1/0.1@diego/testing option Boost:thread.multi to on
but it was already assigned to off by Hello0/0.1@diego/testing
WARN: Hello2/0.1@diego/testing tried to change Hello1/0.1@diego/testing option Poco:deps_bundled to What
but it was already assigned to True by Hello0/0.1@diego/testing""", str(output))
        self.assertEqual(self.sut.values.dumps(),
                         """optimized=4
path=NOTDEF
static=False
Boost:static=False
Boost:thread=True
Boost:thread.multi=off
Poco:deps_bundled=True""")


class OptionsValuesTest(unittest.TestCase):

    def setUp(self):
        self.sut = OptionsValues.loads("""static=True
        optimized=3
        Poco:deps_bundled=True
        Boost:static=False
        Boost:thread=True
        Boost:thread.multi=off
        """)

    def test_from_list(self):
        option_values = OptionsValues.from_list(self.sut.as_list())
        self.assertEqual(option_values.dumps(), self.sut.dumps())

    def test_dumps(self):
        self.assertEqual(self.sut.dumps(), "\n".join(["optimized=3",
                                                      "static=True",
                                                      "Boost:static=False",
                                                      "Boost:thread=True",
                                                      "Boost:thread.multi=off",
                                                      "Poco:deps_bundled=True"]))

    def test_sha_constant(self):
        self.assertEqual(self.sut.sha({"Boost", "Poco"}),
                         "7e406fc70a1c40b597353b39a0c0a605e9f95332")
        self.sut.new_option = False
        self.sut["Boost"].new_option = "off"
        self.sut["Poco"].new_option = 0

        self.assertEqual(self.sut.dumps(), "\n".join(["new_option=False",
                                                      "optimized=3",
                                                      "static=True",
                                                      "Boost:new_option=off",
                                                      "Boost:static=False",
                                                      "Boost:thread=True",
                                                      "Boost:thread.multi=off",
                                                      "Poco:deps_bundled=True",
                                                      "Poco:new_option=0"]))
        self.assertEqual(self.sut.sha({"Boost", "Poco"}),
                         "7e406fc70a1c40b597353b39a0c0a605e9f95332")

