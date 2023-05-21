import textwrap

import pytest

from conans.errors import ConanException
from conans.model.options import Options
from conans.model.recipe_ref import RecipeReference


class TestOptions:

    @pytest.fixture(autouse=True)
    def _setup(self):
        options = {"static": [True, False], "optimized": [2, 3, 4], "path": ["ANY"]}
        values = {"static": True, "optimized": 3, "path": "mypath"}
        self.sut = Options(options, values)

    def test_booleans(self):
        assert self.sut.static
        assert self.sut.static == True
        assert self.sut.static != False
        assert bool(self.sut.static)

        assert self.sut.optimized
        assert self.sut.optimized == 3
        assert self.sut.optimized != 2

        assert self.sut.path == "mypath"
        assert self.sut.path != "otherpath"

    def test_invalid_value(self):
        with pytest.raises(ConanException) as e:
            assert self.sut.static != 1
        assert "'1' is not a valid 'options.static' value" in str(e.value)

        with pytest.raises(ConanException) as e:
            assert self.sut.optimized != 5
        assert "'5' is not a valid 'options.optimized' value" in str(e.value)

        with pytest.raises(ConanException) as e:
            self.sut.static = 1
        assert "'1' is not a valid 'options.static' value" in str(e.value)

        with pytest.raises(ConanException) as e:
            self.sut.optimized = 5
        assert "'5' is not a valid 'options.optimized' value" in str(e.value)

    def test_non_existing_option(self):
        with pytest.raises(ConanException) as e:
            assert self.sut.potato
        assert "option 'potato' doesn't exist" in str(e.value)

    def test_int(self):
        assert 3 == int(self.sut.optimized)

    def test_in(self):
        assert "static" in self.sut
        assert "potato" not in self.sut
        assert "optimized" in self.sut
        assert "path" in self.sut

    def test_assign(self):
        self.sut.static = False
        self.sut.optimized = 2
        self.sut.optimized = "4"
        self.sut.path = "otherpath"

        assert not self.sut.static
        assert self.sut.optimized == 4
        assert self.sut.path == "otherpath"

    def test_dumps(self):
        text = self.sut.dumps()
        # Output is ordereded alphabetically
        expected = textwrap.dedent("""\
            optimized=3
            path=mypath
            static=True""")
        assert text == expected

    def test_freeze(self):
        assert self.sut.static

        self.sut.freeze()
        # Should be freezed now
        # same value should not raise
        self.sut.static = True

        # Different value should raise
        with pytest.raises(ConanException) as e:
            self.sut.static = False
        assert "Incorrect attempt to modify option 'static'" in str(e.value)
        assert "static=True" in self.sut.dumps()

        # Removal of options with values doesn't raise anymore
        del self.sut.static
        assert "static" not in self.sut.dumps()

        # Test None is possible to change
        sut2 = Options({"static": [True, False],
                        "other": [True, False]})
        sut2.freeze()
        sut2.static = True
        assert "static=True" in sut2.dumps()
        # But not twice
        with pytest.raises(ConanException) as e:
            sut2.static = False
        assert "Incorrect attempt to modify option 'static'" in str(e.value)
        assert "static=True" in sut2.dumps()

        # can remove other, removing is always possible, even if freeze
        del sut2.other
        assert "other" not in sut2.dumps()


class TestOptionsLoad:
    def test_load(self):
        text = textwrap.dedent("""\
            optimized=3
            path=mypath
            static=True
            zlib*:option=8
            *:common=value
            """)
        sut = Options.loads(text)
        assert sut.optimized == 3
        assert sut.optimized != "whatever"  # Non validating
        assert sut.path == "mypath"
        assert sut.path != "whatever"  # Non validating
        assert sut.static == "True"
        assert sut.static != "whatever"  # Non validating
        assert sut["zlib*"].option == 8
        assert sut["zlib*"].option != "whatever"  # Non validating
        assert sut["*"].common == "value"
        assert sut["*"].common != "whatever"  # Non validating


class TestOptionsPropagate:
    def test_basic(self):
        options = {"static": [True, False]}
        values = {"static": True}
        sut = Options(options, values)
        assert sut.static

        ref = RecipeReference.loads("boost/1.0")
        # if ref!=None option MUST be preceded by boost:
        down_options = Options(options_values={"zlib/2.0:other": 1, "boost/1.0:static": False})
        sut.apply_downstream(down_options, Options(), ref, False)
        assert not sut.static

        # Should be freezed now
        with pytest.raises(ConanException) as e:
            sut.static = True
        assert "Incorrect attempt to modify option 'static'" in str(e.value)

        self_options, up_options = sut.get_upstream_options(down_options, ref, False)
        assert up_options.dumps() == "zlib/2.0:other=1"
        assert self_options.dumps() == "boost/1.0:static=False\nzlib/2.0:other=1"


class TestOptionsNone:
    @pytest.fixture(autouse=True)
    def _setup(self):
        options = {"static": [None, 1, 2], "other": [None, "ANY"], "more": ["None", 1]}
        self.sut = Options(options)

    def test_booleans(self):
        assert self.sut.static == None
        assert not self.sut.static
        assert self.sut.static != 1
        assert self.sut.static != 2
        with pytest.raises(ConanException) as e:
            self.sut.static == 3
        assert "'3' is not a valid 'options.static' value" in str(e.value)

        with pytest.raises(ConanException) as e:
            self.sut.static == "None"
        assert "'None' is not a valid 'options.static' value" in str(e.value)

        assert self.sut.other == None
        assert self.sut.other != "whatever"  # dont raise, ANY
        self.sut.other = None
        assert self.sut.other == None

        assert not self.sut.more
        assert self.sut.more == None
        assert self.sut.more != 1
        with pytest.raises(ConanException) as e:
            self.sut.more == 2
        assert "'2' is not a valid 'options.more' value" in str(e.value)
        with pytest.raises(ConanException) as e:
            self.sut.more = None
        assert "'None' is not a valid 'options.more' value" in str(e.value)
        self.sut.more = "None"
        assert not self.sut.more  # This is still evaluated to false, like OFF, 0, FALSE, etc
        assert self.sut.more == "None"
        assert self.sut.more != None

    def test_assign(self):
        self.sut.static = 1
        assert self.sut.static == 1

    def test_dumps(self):
        text = self.sut.dumps()
        assert text == ""

    def test_boolean_none(self):
        options = Options({"static": [None, "None", 1, 2]})
        assert options.static != 1
        assert not (options.static == 1)
        assert options.static != "None"
        assert not (options.static == "None")
        assert options.static == None
        assert not (options.static != None)

        options.static = "None"
        assert options.static == "None"
        assert not (options.static != "None")
        assert not (options.static == None)
        assert options.static != None

'''
    def test_undefined_value(self):
        """ Not assigning a value to options will raise an error at validate() step
        """
        package_options = PackageOptions.loads("""{
        path: ANY}""")
        with self.assertRaisesRegex(ConanException, option_undefined_msg("path")):
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
                   "hello1": hello1_values}
        down_ref = RecipeReference.loads("hello0/0.1@diego/testing")
        own_ref = RecipeReference.loads("hello1/0.1@diego/testing")
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
                    "hello1": hello1_values}
        down_ref = RecipeReference.loads("hello2/0.1@diego/testing")

        with self.assertRaisesRegex(ConanException, "hello2/0.1@diego/testing tried to change "
                                     "hello1/0.1@diego/testing option optimized to 2"):
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
        own_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = RecipeReference.loads("consumer/0.1@diego/testing")
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
        own_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = RecipeReference.loads("consumer/0.1@diego/testing")
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
        own_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = RecipeReference.loads("consumer/0.1@diego/testing")
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
        own_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
        down_ref = RecipeReference.loads("consumer/0.1@diego/testing")
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
        down_ref = RecipeReference.loads("consumer/0.1@diego/testing")
        own_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
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
        down_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
        own_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
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
        sut = Options.create_options({"opt": [None, "a", "b"]}, {"opt": "a"})

        other_options = PackageOptionValues()
        other_options.add_option("opt", None)
        options = {"whatever.*": other_options}
        down_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
        own_ref = RecipeReference.loads("Boost.Assert/0.1@diego/testing")
        sut.propagate_upstream(options, down_ref, own_ref)
        self.assertEqual(sut.values.as_list(), [("opt", "a"),
                                                ("whatever.*:opt", "None"),
                                                ])

    def test_propagate_in_pacakge_options(self):
        package_options = Options.create_options({"opt": [None, "a", "b"]}, None)
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

    @pytest.mark.xfail(reason="Working in the PackageID broke this")
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
        emsg = "not enough values to unpack"
        with self.assertRaisesRegex(ValueError, emsg):
            OptionsValues.loads("a=2\nconfig\nb=3")

        with self.assertRaisesRegex(ValueError, emsg):
            OptionsValues.loads("config\na=2\ncommit\nb=3")

    def test_exceptions_empty_value(self):
        emsg = "not enough values to unpack"
        with self.assertRaisesRegex(ValueError, emsg):
            OptionsValues("a=2\nconfig\nb=3")

        with self.assertRaisesRegex(ValueError, emsg):
            OptionsValues(("a=2", "config"))

        with self.assertRaisesRegex(ValueError, emsg):
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
'''
