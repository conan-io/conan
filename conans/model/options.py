
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
        if self._value is None and self._possible_values is not None \
                and None not in self._possible_values:
            raise ConanException(option_undefined_msg(self._name))


class _PackageOptions:
    def __init__(self, recipe_options_definition=None, constrained=False):
        self._constrained = constrained
        definition = recipe_options_definition or {}
        self._data = {str(option): _PackageOption(str(option), None, possible_values)
                      for option, possible_values in definition.items()}
        self._freeze = False

    def clear(self):
        # for header_only() clearing
        if self._freeze:
            raise ConanException(f"Incorrect attempt to modify options.clear()")
        self._data.clear()

    def freeze(self):
        self._freeze = True

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

    def _ensure_exists(self, field):
        if self._constrained and field not in self._data:
            raise ConanException(option_not_exist_msg(field, list(self._data.keys())))

    def __getattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        self._ensure_exists(field)
        return self._data[field]

    def __delattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        if self._freeze:
            raise ConanException(f"Incorrect attempt to modify options '{field}'")
        self._ensure_exists(field)
        del self._data[field]

    def __setattr__(self, field, value):
        if field[0] == "_" or field.startswith("values"):
            return super(_PackageOptions, self).__setattr__(field, value)
        self._set(field, value)

    def __setitem__(self, item, value):
        self._set(item, value)

    def _set(self, item, value):
        # programmatic way to define values, for Conan codebase
        if self._freeze:
            raise ConanException(f"Incorrect attempt to modify options '{item}'")
        self._ensure_exists(item)
        self._data.setdefault(item, _PackageOption(item, None)).value = value

    def items(self):
        result = []
        for field, package_option in sorted(list(self._data.items())):
            result.append((field, package_option.value))
        return result

    def update_options(self, other, is_pattern=False):
        """
        @param is_pattern: if True, then the value might not exist and won't be updated
        @type other: _PackageOptions
        """
        for k, v in other._data.items():
            if is_pattern and k not in self._data:
                continue
            self._set(k, v)


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

    def scope(self, name):
        package_options = self._deps_package_options.setdefault(name, _PackageOptions())
        package_options.update_options(self._package_options)
        self._package_options = _PackageOptions()

    def dumps(self):
        result = []
        for key, value in self._package_options.items():
            result.append("%s=%s" % (key, value))
        for pkg, pkg_option in self._deps_package_options.items():
            for key, value in pkg_option.items():
                result.append("%s:%s=%s" % (pkg, key, value))
        return "\n".join(result)

    def clear(self):
        # for header_only() clearing
        self._package_options.clear()
        self._deps_package_options.clear()

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

    def apply_downstream(self, down_options, profile_options, own_ref):
        assert isinstance(down_options, Options), type(down_options)
        assert isinstance(profile_options, Options), type(down_options)

        for defined_options in down_options, profile_options:
            if own_ref is None:
                self._package_options.update_options(defined_options._package_options)
            else:
                for pattern, options in defined_options._deps_package_options.items():
                    if pattern == own_ref.name:  # exact match
                        self._package_options.update_options(options)
                    elif fnmatch.fnmatch(own_ref.name, pattern):  # approx match
                        self._package_options.update_options(options, is_pattern=True)
        self._package_options.freeze()

    def get_upstream_options(self, down_options, own_ref):
        assert isinstance(down_options, Options)

        # write the down
        for pattern, options in down_options._deps_package_options.items():
            if pattern == own_ref.name:  # exact match
                continue
            self._deps_package_options.setdefault(pattern, _PackageOptions()).update_options(options)

        upstream = Options()
        upstream._deps_package_options = self._deps_package_options.copy()
        self._deps_package_options.clear()
        return upstream

    def validate(self):
        return self._package_options.validate()

    @property
    def sha(self):
        result = ["[options]"]
        d = self.dumps()
        if d:
            result.append(d)
        return '\n'.join(result)
