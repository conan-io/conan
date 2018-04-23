import unittest
from conans.model.options import OptionsValues, PackageOptions, Options, PackageOptionValues,\
    option_undefined_msg
from conans.model.ref import ConanFileReference
from conans.errors import ConanException


class OptionsTest(unittest.TestCase):

    def setUp(self):
        package_options = PackageOptions.loads("""{static: [True, False],
        optimized: [2, 3, 4],
        path: ANY}""")
        values = PackageOptionValues()
        values.add_option("static", True)
        values.add_option("optimized", 3)
        values.add_option("path", "NOTDEF")
        package_options.values = values
        self.sut = Options(package_options)

    def test_int(self):
        self.assertEqual(3, int(self.sut.optimized))

    def test_in(self):
        package_options = PackageOptions.loads("{static: [True, False]}")
        sut = Options(package_options)
        self.assertTrue("static" in sut)
        self.assertFalse("shared" in sut)
        self.assertTrue("shared" not in sut)
        self.assertFalse("static" not in sut)

    def undefined_value_test(self):
        """ Not assigning a value to options will raise an error at validate() step
        """
        package_options = PackageOptions.loads("""{
        path: ANY}""")
        with self.assertRaisesRegexp(ConanException, option_undefined_msg("path")):
            package_options.validate()
        package_options.path = "Something"
        package_options.validate()

    def undefined_value_none_test(self):
        """ The value None is allowed as default, not necessary to default to it
        """
        package_options = PackageOptions.loads('{path: [None, "Other"]}')
        package_options.validate()
        package_options = PackageOptions.loads('{path: ["None", "Other"]}')
        package_options.validate()

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
        boost_values = PackageOptionValues()
        boost_values.add_option("static", False)
        boost_values.add_option("thread", True)
        boost_values.add_option("thread.multi", "off")
        poco_values = PackageOptionValues()
        poco_values.add_option("deps_bundled", True)
        hello1_values = PackageOptionValues()
        hello1_values.add_option("static", False)
        hello1_values.add_option("optimized", 4)

        options = {"Boost": boost_values,
                   "Poco": poco_values,
                   "Hello1": hello1_values}
        down_ref = ConanFileReference.loads("Hello0/0.1@diego/testing")
        own_ref = ConanFileReference.loads("Hello1/0.1@diego/testing")
        self.sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(self.sut.values.as_list(), [("optimized", "4"),
                                                     ("path", "NOTDEF"),
                                                     ("static", "False"),
                                                     ("Boost:static", "False"),
                                                     ("Boost:thread", "True"),
                                                     ("Boost:thread.multi", "off"),
                                                     ("Poco:deps_bundled", "True")])

        boost_values = PackageOptionValues()
        boost_values.add_option("static", 2)
        boost_values.add_option("thread", "Any")
        boost_values.add_option("thread.multi", "on")
        poco_values = PackageOptionValues()
        poco_values.add_option("deps_bundled", "What")
        hello1_values = PackageOptionValues()
        hello1_values.add_option("static", True)
        hello1_values.add_option("optimized", "2")
        options2 = {"Boost": boost_values,
                    "Poco": poco_values,
                    "Hello1": hello1_values}
        down_ref = ConanFileReference.loads("Hello2/0.1@diego/testing")

        with self.assertRaisesRegexp(ConanException, "Hello2/0.1@diego/testing tried to change "
                                     "Hello1/0.1@diego/testing option optimized to 2"):
            self.sut.propagate_upstream(options2, down_ref, own_ref)

        self.assertEqual(self.sut.values.dumps(),
                         """optimized=4
path=NOTDEF
static=False
Boost:static=False
Boost:thread=True
Boost:thread.multi=off
Poco:deps_bundled=True""")

    def pattern_positive_test(self):
        boost_values = PackageOptionValues()
        boost_values.add_option("static", False)
        boost_values.add_option("path", "FuzzBuzz")

        options = {"Boost.*": boost_values}
        own_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = ConanFileReference.loads("Consumer/0.1@diego/testing")
        self.sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(self.sut.values.as_list(), [("optimized", "3"),
                                                     ("path", "FuzzBuzz"),
                                                     ("static", "False"),
                                                     ("Boost.*:path", "FuzzBuzz"),
                                                     ("Boost.*:static", "False"),
                                                     ])

    def multi_pattern_test(self):
        boost_values = PackageOptionValues()
        boost_values.add_option("static", False)
        boost_values.add_option("path", "FuzzBuzz")
        boost_values2 = PackageOptionValues()
        boost_values2.add_option("optimized", 2)

        options = {"Boost.*": boost_values,
                   "*": boost_values2}
        own_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = ConanFileReference.loads("Consumer/0.1@diego/testing")
        self.sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(self.sut.values.as_list(), [("optimized", "2"),
                                                     ("path", "FuzzBuzz"),
                                                     ("static", "False"),
                                                     ('*:optimized', '2'),
                                                     ("Boost.*:path", "FuzzBuzz"),
                                                     ("Boost.*:static", "False"),
                                                     ])

    def multi_pattern_error_test(self):
        boost_values = PackageOptionValues()
        boost_values.add_option("optimized", 4)
        boost_values2 = PackageOptionValues()
        boost_values2.add_option("optimized", 2)

        options = {"Boost.*": boost_values,
                   "*": boost_values2}
        own_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = ConanFileReference.loads("Consumer/0.1@diego/testing")
        self.sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(self.sut.values.as_list(), [('optimized', '4'),
                                                     ('path', 'NOTDEF'),
                                                     ('static', 'True'),
                                                     ('*:optimized', '2'),
                                                     ('Boost.*:optimized', '4')])

    def all_positive_test(self):
        boost_values = PackageOptionValues()
        boost_values.add_option("static", False)
        boost_values.add_option("path", "FuzzBuzz")

        options = {"*": boost_values}
        own_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = ConanFileReference.loads("Consumer/0.1@diego/testing")
        self.sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(self.sut.values.as_list(), [("optimized", "3"),
                                                     ("path", "FuzzBuzz"),
                                                     ("static", "False"),
                                                     ("*:path", "FuzzBuzz"),
                                                     ("*:static", "False"),
                                                     ])

    def pattern_ignore_test(self):
        boost_values = PackageOptionValues()
        boost_values.add_option("fake_option", "FuzzBuzz")

        options = {"Boost.*": boost_values}
        down_ref = ConanFileReference.loads("Consumer/0.1@diego/testing")
        own_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        self.sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(self.sut.values.as_list(), [("optimized", "3"),
                                                     ("path", "NOTDEF"),
                                                     ("static", "True"),
                                                     ("Boost.*:fake_option", "FuzzBuzz"),
                                                     ])

    def pattern_unmatch_test(self):
        boost_values = PackageOptionValues()
        boost_values.add_option("fake_option", "FuzzBuzz")

        options = {"OpenSSL.*": boost_values}
        down_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        own_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        self.sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(self.sut.values.as_list(), [("optimized", "3"),
                                                     ("path", "NOTDEF"),
                                                     ("static", "True"),
                                                     ("OpenSSL.*:fake_option", "FuzzBuzz"),
                                                     ])


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
        option_values = OptionsValues(self.sut.as_list())
        self.assertEqual(option_values.dumps(), self.sut.dumps())

    def test_dumps(self):
        self.assertEqual(self.sut.dumps(), "\n".join(["optimized=3",
                                                      "static=True",
                                                      "Boost:static=False",
                                                      "Boost:thread=True",
                                                      "Boost:thread.multi=off",
                                                      "Poco:deps_bundled=True"]))

    def test_sha_constant(self):
        self.assertEqual(self.sut.sha,
                         "2442d43f1d558621069a15ff5968535f818939b5")
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
        self.assertEqual(self.sut.sha,
                         "2442d43f1d558621069a15ff5968535f818939b5")
