import sys
import unittest

import pytest
import six

from conans.errors import ConanException
from conans.model.options import Options, OptionsValues, PackageOptionValues, PackageOptions, \
    option_undefined_msg
from conans.model.ref import ConanFileReference


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

    def test_undefined_value(self):
        """ Not assigning a value to options will raise an error at validate() step
        """
        package_options = PackageOptions.loads("""{
        path: ANY}""")
        with six.assertRaisesRegex(self, ConanException, option_undefined_msg("path")):
            package_options.validate()
        package_options.path = "Something"
        package_options.validate()

    def test_undefined_value_none(self):
        """ The value None is allowed as default, not necessary to default to it
        """
        package_options = PackageOptions.loads('{path: [None, "Other"]}')
        package_options.validate()
        package_options = PackageOptions.loads('{path: ["None", "Other"]}')
        package_options.validate()

    def test_items(self):
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "NOTDEF"),
                                            ("static", "True")])
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "NOTDEF"),
                                            ("static", "True")])

    def test_change(self):
        self.sut.path = "C:/MyPath"
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "C:/MyPath"),
                                            ("static", "True")])
        self.assertEqual(self.sut.items(), [("optimized", "3"), ("path", "C:/MyPath"),
                                            ("static", "True")])
        with six.assertRaisesRegex(self, ConanException,
                                     "'5' is not a valid 'options.optimized' value"):
            self.sut.optimized = 5

    def test_boolean(self):
        self.sut.static = False
        self.assertFalse(self.sut.static)
        self.assertTrue(not self.sut.static)
        self.assertTrue(self.sut.static == False)
        self.assertFalse(self.sut.static == True)
        self.assertFalse(self.sut.static != False)
        self.assertTrue(self.sut.static != True)
        self.assertTrue(self.sut.static == "False")
        self.assertTrue(self.sut.static != "True")

    def test_basic(self):
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

        with six.assertRaisesRegex(self, ConanException, "Hello2/0.1@diego/testing tried to change "
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

    def test_pattern_positive(self):
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

    def test_multi_pattern(self):
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

    def test_multi_pattern_error(self):
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

    def test_all_positive(self):
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

    def test_pattern_ignore(self):
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

    def test_pattern_unmatch(self):
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

    def test_get_safe_options(self):
        self.assertEqual(True, self.sut.get_safe("static"))
        self.assertEqual(3, self.sut.get_safe("optimized"))
        self.assertEqual("NOTDEF", self.sut.get_safe("path"))
        self.assertEqual(None, self.sut.get_safe("unknown"))
        self.sut.path = "None"
        self.sut.static = False
        self.assertEqual(False, self.sut.get_safe("static"))
        self.assertEqual("None", self.sut.get_safe("path"))
        self.assertEqual(False, self.sut.get_safe("static", True))
        self.assertEqual("None", self.sut.get_safe("path", True))
        self.assertEqual(True, self.sut.get_safe("unknown", True))


class OptionsValuesPropagationUpstreamNone(unittest.TestCase):

    def test_propagate_in_options(self):
        package_options = PackageOptions.loads("""{opt: [None, "a", "b"],}""")
        values = PackageOptionValues()
        values.add_option("opt", "a")
        package_options.values = values
        sut = Options(package_options)

        other_options = PackageOptionValues()
        other_options.add_option("opt", None)
        options = {"whatever.*": other_options}
        down_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        own_ref = ConanFileReference.loads("Boost.Assert/0.1@diego/testing")
        sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(sut.values.as_list(), [("opt", "a"),
                                                ("whatever.*:opt", "None"),
                                                ])

    def test_propagate_in_pacakge_options(self):
        package_options = PackageOptions.loads("""{opt: [None, "a", "b"],}""")
        values = PackageOptionValues()
        package_options.values = values

        package_options.propagate_upstream({'opt': None}, None, None, [])
        self.assertEqual(package_options.values.items(), [('opt', 'None'), ])


class OptionsValuesTest(unittest.TestCase):

    def setUp(self):
        self.sut = OptionsValues.loads("""static=True
        optimized=3
        Poco:deps_bundled=True
        Boost:static=False
        Boost:thread=True
        Boost:thread.multi=off
        """)

    def test_get_safe(self):
        option_values = OptionsValues(self.sut.as_list())
        assert option_values.get_safe("missing") is None
        assert option_values.get_safe("optimized") == 3
        with pytest.raises(ConanException):
            # This is not supported at the moment
            option_values["Boost"].get_safe("thread")

    def test_from_list(self):
        option_values = OptionsValues(self.sut.as_list())
        self.assertEqual(option_values.dumps(), self.sut.dumps())

    def test_from_dict(self):
        options_as_dict = dict([item.split('=') for item in self.sut.dumps().splitlines()])
        option_values = OptionsValues(options_as_dict)
        self.assertEqual(option_values.dumps(), self.sut.dumps())

    def test_consistency(self):
        def _check_equal(hs1, hs2, hs3, hs4):
            opt_values1 = OptionsValues(hs1)
            opt_values2 = OptionsValues(hs2)
            opt_values3 = OptionsValues(hs3)
            opt_values4 = OptionsValues(hs4)

            self.assertEqual(opt_values1.dumps(), opt_values2.dumps())
            self.assertEqual(opt_values1.dumps(), opt_values3.dumps())
            self.assertEqual(opt_values1.dumps(), opt_values4.dumps())

        # Check that all possible input options give the same result
        _check_equal([('opt', 3)],       [('opt', '3'), ],       ('opt=3', ),       {'opt': 3})
        _check_equal([('opt', True)],    [('opt', 'True'), ],    ('opt=True', ),    {'opt': True})
        _check_equal([('opt', False)],   [('opt', 'False'), ],   ('opt=False', ),   {'opt': False})
        _check_equal([('opt', None)],    [('opt', 'None'), ],    ('opt=None', ),    {'opt': None})
        _check_equal([('opt', 0)],       [('opt', '0'), ],       ('opt=0', ),       {'opt': 0})
        _check_equal([('opt', '')],      [('opt', ''), ],        ('opt=', ),        {'opt': ''})

        # Check for leading and trailing spaces
        _check_equal([('  opt  ', 3)], [(' opt  ', '3'), ], ('  opt =3', ), {' opt ': 3})
        _check_equal([('opt', '  value  ')], [('opt', '  value '), ], ('opt= value  ', ),
                     {'opt': ' value '})

        # This is expected behaviour:
        self.assertNotEqual(OptionsValues([('opt', ''), ]).dumps(),
                            OptionsValues(('opt=""', )).dumps())

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

    def test_loads_exceptions(self):
        emsg = "not enough values to unpack" if six.PY3 and sys.version_info.minor > 4 \
            else "need more than 1 value to unpack"
        with six.assertRaisesRegex(self, ValueError, emsg):
            OptionsValues.loads("a=2\nconfig\nb=3")

        with six.assertRaisesRegex(self, ValueError, emsg):
            OptionsValues.loads("config\na=2\ncommit\nb=3")

    def test_exceptions_empty_value(self):
        emsg = "not enough values to unpack" if six.PY3 and sys.version_info.minor > 4 \
            else "need more than 1 value to unpack"
        with six.assertRaisesRegex(self, ValueError, emsg):
            OptionsValues("a=2\nconfig\nb=3")

        with six.assertRaisesRegex(self, ValueError, emsg):
            OptionsValues(("a=2", "config"))

        with six.assertRaisesRegex(self, ValueError, emsg):
            OptionsValues([('a', 2), ('config', ), ])

    def test_exceptions_repeated_value(self):
        try:
            OptionsValues.loads("a=2\na=12\nb=3").dumps()
            OptionsValues(("a=2", "b=23", "a=12"))
            OptionsValues([('a', 2), ('b', True), ('a', '12')])
        except Exception as e:
            self.fail("Not expected exception: {}".format(e))

    def test_package_with_spaces(self):
        self.assertEqual(OptionsValues([('pck2:opt', 50), ]).dumps(),
                         OptionsValues([('pck2 :opt', 50), ]).dumps())


def test_validate_any_as_list():
    package_options = PackageOptions.loads("""{
    path: ["ANY", "kk"]}""")
    values = PackageOptionValues()
    values.add_option("path", "FOO")
    package_options.values = values
    sut = Options(package_options)
    assert sut.path == "FOO"

    package_options = PackageOptions.loads("""{
        path: "ANY"}""")
    values = PackageOptionValues()
    values.add_option("path", "WHATEVER")
    package_options.values = values
    sut = Options(package_options)
    assert sut.path == "WHATEVER"
