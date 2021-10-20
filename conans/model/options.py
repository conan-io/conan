
import fnmatch

from conans.errors import ConanException

_falsey_options = ["false", "none", "0", "off", ""]


def option_not_exist_msg(option_name, existing_options):
    """ Someone is referencing an option that is not available in the current package
    options
    """
    result = ["option '%s' doesn't exist" % option_name,
              "Possible options are %s" % existing_options or "none"]
    return "\n".join(result)


def option_undefined_msg(name):
    return "'%s' value not defined" % name


class _PackageOption:
    def __init__(self, name, value, possible_values=None):
        self._name = name
        self._value = value  # Value None = not defined
        # possible_values only possible origin is recipes
        if possible_values is None or possible_values == "ANY":
            self._possible_values = None
        else:
            self._possible_values = [str(v) if v is not None else None for v in possible_values]

    def get_info_options(self):
        return _PackageOption(self._name, self._value)

    def __bool__(self):
        if self._value is None:
            return False
        return self._value.lower() not in _falsey_options

    def __str__(self):
        return str(self._value)

    def __int__(self):
        return int(self._value)

    def _check_valid_value(self, value):
        """ checks that the provided value is allowed by current restrictions
        """
        if self._possible_values is not None and value not in self._possible_values:
            msg = ("'%s' is not a valid 'options.%s' value.\nPossible values are %s"
                   % (value, self._name, self._possible_values))
            raise ConanException(msg)

    def __eq__(self, other):
        # To promote the other to string, and always compare as strings
        # if self.options.myoption == 1 => will convert 1 to "1"
        other = str(other) if other is not None else None
        self._check_valid_value(other)
        return other == self.__str__()

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = str(v) if v is not None else None
        self._check_valid_value(v)
        self._value = v

    def validate(self):
        # check that this has a valid option value defined
        if self._value is None and None not in self._possible_values:
            raise ConanException(option_undefined_msg(self._name))


class _PackageOptions:
    def __init__(self, recipe_options_definition=None, constrained=False):
        self._constrained = constrained
        definition = recipe_options_definition or {}
        self._data = {str(option): _PackageOption(str(option), None, possible_values)
                      for option, possible_values in definition.items()}

    def __contains__(self, option):
        return str(option) in self._data

    def get_safe(self, field, default=None):
        return self._data.get(field, default)

    def validate(self):
        for child in self._data.values():
            child.validate()

    def get_info_options(self):
        result = _PackageOptions()
        for k, v in self._data.items():
            result._data[k] = v.get_info_options()
        return result

    @property
    def fields(self):
        return sorted(list(self._data.keys()))

    def remove(self, item):
        if not isinstance(item, (list, tuple, set)):
            item = [item]
        for it in item:
            it = str(it)
            self._data.pop(it, None)

    def clear(self):
        self._data = {}

    def _ensure_exists(self, field):
        if self._constrained and field not in self._data:
            raise ConanException(option_not_exist_msg(field, list(self._data.keys())))

    def __getattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        self._ensure_exists(field)
        return self._data[field]

    def __delattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        self._ensure_exists(field)
        del self._data[field]

    def __setattr__(self, field, value):
        if field[0] == "_" or field.startswith("values"):
            return super(_PackageOptions, self).__setattr__(field, value)

        self._ensure_exists(field)
        self._data[field].value = value

    def __setitem__(self, item, value):
        # programmatic way to define values, for Conan codebase
        self._ensure_exists(item)
        self._data.setdefault(item, _PackageOption(item, None)).value = value

    def items(self):
        result = []
        for field, package_option in sorted(list(self._data.items())):
            result.append((field, package_option.value))
        return result

    def initialize_patterns(self, values):
        # Need to apply only those that exists
        for option, value in values.items():
            if option in self._data:
                self._data[option].value = value

    def propagate_upstream(self, package_values, down_ref, own_ref, pattern_options):
        """
        :param: package_values: PackageOptionValues({"shared": "True"}
        :param: pattern_options: Keys from the "package_values" e.g. ["shared"] that shouldn't raise
                                 if they are not existing options for the current object
        """
        if not package_values:
            return

        for name, value in package_values.items():
            if name in pattern_options:  # If it is a pattern-matched option, should check field
                if name in self._data:
                    self._data[name].value = value
            else:
                self._ensure_exists(name)
                self._data[name].value = value

    def update_options(self, other):
        """
        @type other: _PackageOptions
        """
        for k, v in other._data.items():
            self._data.setdefault(k, _PackageOption(str(k), None)).value = v


class Options:
    """ All options of a package, both its own options and the upstream ones.
    Owned by ConanFile.
    """
    def __init__(self, options=None, options_values=None, constrained=True):
        try:
            self._package_options = _PackageOptions(options, constrained)
            # Addressed only by name, as only 1 configuration is allowed
            # if more than 1 is present, 1 should be "private" requirement and its options
            # are not public, not overridable
            self._deps_package_options = {}  # {name("Boost": PackageOptions}
            if options_values:
                for k, v in options_values.items():
                    k = str(k).strip()
                    v = str(v).strip()
                    tokens = k.split(":", 1)
                    if len(tokens) == 2:
                        package, option = tokens
                        self._deps_package_options.setdefault(package, _PackageOptions())[option] = v
                    else:
                        self._package_options[k] = v
        except Exception as e:
            raise ConanException("Error while initializing options. %s" % str(e))

    @staticmethod
    def loads(text):
        """ parses a multiline text in the form, no validation here
        Package:option=value
        other_option=3
        OtherPack:opt3=12.1
        """
        values = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, value = line.split("=", 1)
            values[name] = value
        return Options(options_values=values, constrained=False)

    def dumps(self):
        result = []
        for key, value in self._package_options.items():
            result.append("%s=%s" % (key, value))
        for pkg, pkg_option in self._deps_package_options.items():
            for key, value in pkg_option.items():
                result.append("%s:%s=%s" % (pkg, key, value))
        return "\n".join(result)

    def serialize(self):
        return {k: str(v) for k, v in self._package_options.items()}

    def get_info_options(self, clear_deps=False):
        # To generate the cpp_info.options copy, that can destroy, change and remove things
        result = Options()
        result._package_options = self._package_options.get_info_options()
        if not clear_deps:
            for k, v in self._deps_package_options.items():
                result._deps_package_options[k] = v.get_info_options()
        return result

    def update_options(self, other):
        """
        @type other: Options
        """
        self._package_options.update_options(other._package_options)
        for pkg, pkg_option in other._deps_package_options.items():
            self._deps_package_options.setdefault(pkg, _PackageOptions()).update_options(pkg_option)

    def __contains__(self, option):
        return option in self._package_options

    def __getitem__(self, item):
        return self._deps_package_options.setdefault(item, _PackageOptions())

    def __getattr__(self, attr):
        return getattr(self._package_options, attr)

    def __setattr__(self, attr, value):
        if attr[0] == "_" or attr == "values":
            return super(Options, self).__setattr__(attr, value)
        return setattr(self._package_options, attr, value)

    def __delattr__(self, field):
        try:
            self._package_options.__delattr__(field)
        except ConanException:
            pass

    def propagate_upstream(self, down_package_values, own_ref):
        """ used to propagate from downstream the options to the upper requirements
        :param: down_package_values => {"*": PackageOptionValues({"shared": "True"})}
        :param: own_ref: Reference of the current package => ConanFileReference
        """
        if not down_package_values:
            return

        assert isinstance(down_package_values, dict)
        option_values = _PackageOptions()
        # First step is to accumulate all matching patterns, in sorted()=alphabetical order
        # except the exact match

        for package_pattern, package_option_values in sorted(down_package_values.items()):
            if own_ref.name != package_pattern and fnmatch.fnmatch(own_ref.name, package_pattern):
                option_values.update(package_option_values)
        # These are pattern options, shouldn't raise if not existing
        pattern_options = list(option_values.keys())
        # Now, update with the exact match, that has higher priority
        down_options = down_package_values.get(own_ref.name)
        if down_options is not None:
            option_values.update(down_options)

        self._package_options.propagate_upstream(option_values, pattern_options=pattern_options)

        # Upstream propagation to deps
        for name, option_values in sorted(list(down_package_values.items())):
            if name != own_ref.name:
                pkg_values = self._deps_package_values.setdefault(name, _PackageOptions())
                pkg_values.propagate_upstream(option_values)

    def validate(self):
        return self._package_options.validate()

    def clear_unused(self, refs):
        """ remove all options not related to the passed references,
        that should be the upstream requirements
        """
        # TODO
        existing_names = [pref.ref.name for pref in prefs]
        self._deps_package_options = {k: v for k, v in self._deps_package_options.items()
                                      if k in existing_names}

    @property
    def sha(self):
        result = ["[options]"]
        d = self.dumps()
        if d:
            result.append(d)
        return '\n'.join(result)
