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

    def test_items(self):
        assert self.sut.items() == [("optimized", "3"), ("path", "mypath"), ("static", "True")]
        assert self.sut.items() == [("optimized", "3"), ("path", "mypath"), ("static", "True")]

    def test_get_safe_options(self):
        assert True == self.sut.get_safe("static")
        assert 3 == self.sut.get_safe("optimized")
        assert "mypath" == self.sut.get_safe("path")
        assert None == self.sut.get_safe("unknown")
        self.sut.path = "None"
        self.sut.static = False
        assert False == self.sut.get_safe("static")
        assert "None" == self.sut.get_safe("path")
        assert False == self.sut.get_safe("static", True)
        assert "None" == self.sut.get_safe("path", True)
        assert True == self.sut.get_safe("unknown", True)


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

        self_options, up_options, up_private = sut.get_upstream_options(down_options, ref, False)
        assert up_options.dumps() == "zlib/2.0:other=1"
        assert self_options.dumps() == "boost/1.0:static=False\nzlib/2.0:other=1"
        assert up_private.dumps() == ""


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

    def test_undefined_value(self):
        """ Not assigning a value to options will raise an error at validate() step
        """
        package_options = Options({"path": ["ANY"]})
        with pytest.raises(ConanException):
            package_options.validate()
        package_options.path = "Something"
        package_options.validate()

    def test_undefined_value_none(self):
        """ The value None is allowed as default, not necessary to default to it
        """
        package_options = Options({"path": [None, "Other"]})
        package_options.validate()
        package_options = Options({"path": ["None", "Other"]})
        with pytest.raises(ConanException):  # Literal "None" string not good to be undefined
            package_options.validate()
