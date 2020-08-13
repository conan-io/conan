
import fnmatch

import six
import yaml

from conans.errors import ConanException
from conans.util.sha import sha1

_falsey_options = ["false", "none", "0", "off", ""]


def option_wrong_value_msg(name, value, value_range):
    """ The provided value is not among the range of values that it should
    be
    """
    return ("'%s' is not a valid 'options.%s' value.\nPossible values are %s"
            % (value, name, value_range))


def option_not_exist_msg(option_name, existing_options):
    """ Someone is referencing an option that is not available in the current package
    options
    """
    result = ["option '%s' doesn't exist" % option_name,
              "Possible options are %s" % existing_options or "none"]
    return "\n".join(result)


def option_undefined_msg(name):
    return "'%s' value not defined" % name


class PackageOptionValue(str):
    """ thin wrapper around a string value that allows to check for several false string
    and also promote other types to string for homegeneous comparison
    """
    def __bool__(self):
        return self.lower() not in _falsey_options

    def __nonzero__(self):
        return self.__bool__()

    def __eq__(self, other):
        return str(other).__eq__(self)

    def __ne__(self, other):
        return not self.__eq__(other)


class PackageOptionValues(object):
    """ set of key(string)-value(PackageOptionValue) for options of a package.
    Not prefixed by package name:
    static: True
    optimized: 2
    These are non-validating, not constrained.
    Used for UserOptions, which is a dict{package_name: PackageOptionValues}
    """
    def __init__(self):
        self._dict = {}  # {option_name: PackageOptionValue}
        self._modified = {}
        self._freeze = False

    def __bool__(self):
        return bool(self._dict)

    def __contains__(self, key):
        return key in self._dict

    def __nonzero__(self):
        return self.__bool__()

    def __getattr__(self, attr):
        if attr not in self._dict:
            raise ConanException(option_not_exist_msg(attr, list(self._dict.keys())))
        return self._dict[attr]

    def __delattr__(self, attr):
        if attr not in self._dict:
            return
        del self._dict[attr]

    def clear(self):
        self._dict.clear()

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            return super(PackageOptionValues, self).__setattr__(attr, value)
        self._dict[attr] = PackageOptionValue(value)

    def copy(self):
        result = PackageOptionValues()
        for k, v in self._dict.items():
            result._dict[k] = v
        return result

    @property
    def fields(self):
        return sorted(list(self._dict.keys()))

    def keys(self):
        return self._dict.keys()

    def items(self):
        return sorted(list(self._dict.items()))

    def add(self, option_text):
        assert isinstance(option_text, six.string_types)
        name, value = option_text.split("=")
        self._dict[name.strip()] = PackageOptionValue(value.strip())

    def add_option(self, option_name, option_value):
        self._dict[option_name] = PackageOptionValue(option_value)

    def update(self, other):
        assert isinstance(other, PackageOptionValues)
        self._dict.update(other._dict)

    def remove(self, option_name):
        del self._dict[option_name]

    def freeze(self):
        self._freeze = True

    def propagate_upstream(self, down_package_values, down_ref, own_ref, package_name):
        if not down_package_values:
            return

        assert isinstance(down_package_values, PackageOptionValues)
        for (name, value) in down_package_values.items():
            if name in self._dict and self._dict.get(name) == value:
                continue

            if self._freeze:
                raise ConanException("%s tried to change %s option %s to %s\n"
                                     "but it was already defined as %s"
                                     % (down_ref, own_ref, name, value, self._dict.get(name)))

            modified = self._modified.get(name)
            if modified is not None:
                modified_value, modified_ref = modified
                raise ConanException("%s tried to change %s option %s:%s to %s\n"
                                     "but it was already assigned to %s by %s"
                                     % (down_ref, own_ref, package_name, name, value,
                                        modified_value, modified_ref))
            else:
                self._modified[name] = (value, down_ref)
                self._dict[name] = value

    def serialize(self):
        return self.items()

    @property
    def sha(self):
        result = []
        for name, value in self.items():
            # It is important to discard None values, so migrations in settings can be done
            # without breaking all existing packages SHAs, by adding a first "None" option
            # that doesn't change the final sha
            if value:
                result.append("%s=%s" % (name, value))
        return sha1('\n'.join(result).encode())


class OptionsValues(object):
    """ static= True,
    Boost.static = False,
    Poco.optimized = True
    """
    def __init__(self, values=None):
        self._package_values = PackageOptionValues()
        self._reqs_options = {}  # {name("Boost": PackageOptionValues}
        if not values:
            return

        # convert tuple "Pkg:option=value", "..." to list of tuples(name, value)
        if isinstance(values, tuple):
            values = [item.split("=", 1) for item in values]

        # convert dict {"Pkg:option": "value", "..": "..", ...} to list of tuples (name, value)
        if isinstance(values, dict):
            values = [(k, v) for k, v in values.items()]

        # handle list of tuples (name, value)
        for (k, v) in values:
            k = k.strip()
            v = v.strip() if isinstance(v, six.string_types) else v
            tokens = k.split(":")
            if len(tokens) == 2:
                package, option = tokens
                package_values = self._reqs_options.setdefault(package.strip(),
                                                               PackageOptionValues())
                package_values.add_option(option, v)
            else:
                self._package_values.add_option(k, v)

    def update(self, other):
        self._package_values.update(other._package_values)
        for package_name, package_values in other._reqs_options.items():
            pkg_values = self._reqs_options.setdefault(package_name, PackageOptionValues())
            pkg_values.update(package_values)

    def scope_options(self, name):
        if self._package_values:
            self._reqs_options.setdefault(name, PackageOptionValues()).update(self._package_values)
            self._package_values = PackageOptionValues()

    def descope_options(self, name):
        package_values = self._reqs_options.pop(name, None)
        if package_values:
            self._package_values.update(package_values)

    def clear_unscoped_options(self):
        self._package_values.clear()

    def __contains__(self, item):
        return item in self._package_values

    def __getitem__(self, item):
        return self._reqs_options.setdefault(item, PackageOptionValues())

    def __setitem__(self, item, value):
        self._reqs_options[item] = value

    def pop(self, item):
        return self._reqs_options.pop(item, None)

    def remove(self, name, package=None):
        if package:
            self._reqs_options[package].remove(name)
        else:
            self._package_values.remove(name)

    def __repr__(self):
        return self.dumps()

    def __getattr__(self, attr):
        return getattr(self._package_values, attr)

    def copy(self):
        result = OptionsValues()
        result._package_values = self._package_values.copy()
        for k, v in self._reqs_options.items():
            result._reqs_options[k] = v.copy()
        return result

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            return super(OptionsValues, self).__setattr__(attr, value)
        return setattr(self._package_values, attr, value)

    def __delattr__(self, attr):
        delattr(self._package_values, attr)

    def clear_indirect(self):
        for v in self._reqs_options.values():
            v.clear()

    def filter_used(self, used_pkg_names):
        self._reqs_options = {k: v for k, v in self._reqs_options.items() if k in used_pkg_names}

    def as_list(self):
        result = []
        options_list = self._package_values.items()
        if options_list:
            result.extend(options_list)
        for package_name, package_values in sorted(self._reqs_options.items()):
            for option_name, option_value in package_values.items():
                result.append(("%s:%s" % (package_name, option_name), option_value))
        return result

    def dumps(self):
        result = []
        for key, value in self.as_list():
            result.append("%s=%s" % (key, value))
        return "\n".join(result)

    @staticmethod
    def loads(text):
        """ parses a multiline text in the form
        Package:option=value
        other_option=3
        OtherPack:opt3=12.1
        """
        options = tuple(line.strip() for line in text.splitlines() if line.strip())
        return OptionsValues(options)

    @property
    def sha(self):
        result = [self._package_values.sha]
        for key in sorted(list(self._reqs_options.keys())):
            result.append(self._reqs_options[key].sha)
        return sha1('\n'.join(result).encode())

    def serialize(self):
        ret = {"options": self._package_values.serialize(),
               "req_options": {}}
        for name, values in self._reqs_options.items():
            ret["req_options"][name] = values.serialize()
        return ret

    def clear(self):
        self._package_values.clear()
        self._reqs_options.clear()


class PackageOption(object):
    def __init__(self, possible_values, name):
        self._name = name
        self._value = None
        if possible_values == "ANY":
            self._possible_values = "ANY"
        else:
            self._possible_values = sorted(str(v) for v in possible_values)

    def copy(self):
        result = PackageOption(self._possible_values, self._name)
        return result

    def __bool__(self):
        if not self._value:
            return False
        return self._value.lower() not in _falsey_options

    def __nonzero__(self):
        return self.__bool__()

    def __str__(self):
        return str(self._value)

    def __int__(self):
        return int(self._value)

    def _check_option_value(self, value):
        """ checks that the provided value is allowed by current restrictions
        """
        if self._possible_values != "ANY" and value not in self._possible_values:
            raise ConanException(option_wrong_value_msg(self._name, value, self._possible_values))

    def __eq__(self, other):
        if other is None:
            return self._value is None
        other = str(other)
        self._check_option_value(other)
        return other == self.__str__()

    def __ne__(self, other):
        return not self.__eq__(other)

    def remove(self, values):
        if self._possible_values == "ANY":
            return
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        values = [str(v) for v in values]
        self._possible_values = [v for v in self._possible_values if v not in values]

        if self._value is not None:
            self._check_option_value(self._value)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = str(v)
        self._check_option_value(v)
        self._value = v

    def validate(self):
        if self._value is None and "None" not in self._possible_values:
            raise ConanException(option_undefined_msg(self._name))


class PackageOptions(object):
    def __init__(self, definition):
        definition = definition or {}
        self._data = {str(k): PackageOption(v, str(k))
                      for k, v in definition.items()}
        self._modified = {}
        self._freeze = False

    def copy(self):
        result = PackageOptions(None)
        result._data = {k: v.copy() for k, v in self._data.items()}
        return result

    def __contains__(self, option):
        return str(option) in self._data

    @staticmethod
    def loads(text):
        return PackageOptions(yaml.safe_load(text) or {})

    def get_safe(self, field, default=None):
        return self._data.get(field, default)

    def validate(self):
        for child in self._data.values():
            child.validate()

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
        if field not in self._data:
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
            return super(PackageOptions, self).__setattr__(field, value)

        self._ensure_exists(field)
        self._data[field].value = value

    @property
    def values(self):
        result = PackageOptionValues()
        for field, package_option in self._data.items():
            result.add_option(field, package_option.value)
        return result

    def _items(self):
        result = []
        for field, package_option in sorted(list(self._data.items())):
            result.append((field, package_option.value))
        return result

    def items(self):
        return self._items()

    def iteritems(self):
        return self._items()

    @values.setter
    def values(self, vals):
        assert isinstance(vals, PackageOptionValues)
        for (name, value) in vals.items():
            self._ensure_exists(name)
            self._data[name].value = value

    def initialize_patterns(self, values):
        # Need to apply only those that exists
        for option, value in values.items():
            if option in self._data:
                self._data[option].value = value

    def freeze(self):
        self._freeze = True

    def propagate_upstream(self, package_values, down_ref, own_ref, pattern_options):
        """
        :param: package_values: PackageOptionValues({"shared": "True"}
        :param: pattern_options: Keys from the "package_values" e.g. ["shared"] that shouldn't raise
                                 if they are not existing options for the current object
        """
        if not package_values:
            return

        for (name, value) in package_values.items():
            if name in self._data and self._data.get(name) == value:
                continue

            if self._freeze:
                raise ConanException("%s tried to change %s option %s to %s\n"
                                     "but it was already defined as %s"
                                     % (down_ref, own_ref, name, value, self._data.get(name)))
            modified = self._modified.get(name)
            if modified is not None:
                modified_value, modified_ref = modified
                raise ConanException("%s tried to change %s option %s to %s\n"
                                     "but it was already assigned to %s by %s"
                                     % (down_ref, own_ref, name, value,
                                        modified_value, modified_ref))
            else:
                if name in pattern_options:  # If it is a pattern-matched option, should check field
                    if name in self._data:
                        self._data[name].value = value
                        self._modified[name] = (value, down_ref)
                else:
                    self._ensure_exists(name)
                    self._data[name].value = value
                    self._modified[name] = (value, down_ref)


class Options(object):
    """ All options of a package, both its own options and the upstream ones.
    Owned by ConanFile.
    """
    def __init__(self, options):
        assert isinstance(options, PackageOptions)
        self._package_options = options
        # Addressed only by name, as only 1 configuration is allowed
        # if more than 1 is present, 1 should be "private" requirement and its options
        # are not public, not overridable
        self._deps_package_values = {}  # {name("Boost": PackageOptionValues}

    def copy(self):
        """ deepcopy, same as Settings"""
        result = Options(self._package_options.copy())
        result._deps_package_values = {k: v.copy() for k, v in self._deps_package_values.items()}
        return result

    def freeze(self):
        self._package_options.freeze()
        for v in self._deps_package_values.values():
            v.freeze()

    @property
    def deps_package_values(self):
        return self._deps_package_values

    def clear(self):
        self._package_options.clear()

    def __contains__(self, option):
        return option in self._package_options

    def __getitem__(self, item):
        return self._deps_package_values.setdefault(item, PackageOptionValues())

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

    @property
    def values(self):
        result = OptionsValues()
        result._package_values = self._package_options.values
        for k, v in self._deps_package_values.items():
            result._reqs_options[k] = v.copy()
        return result

    @values.setter
    def values(self, v):
        assert isinstance(v, OptionsValues)
        self._package_options.values = v._package_values
        self._deps_package_values.clear()
        for k, v in v._reqs_options.items():
            self._deps_package_values[k] = v.copy()

    def propagate_upstream(self, down_package_values, down_ref, own_ref):
        """ used to propagate from downstream the options to the upper requirements
        :param: down_package_values => {"*": PackageOptionValues({"shared": "True"})}
        :param: down_ref
        :param: own_ref: Reference of the current package => ConanFileReference
        """
        if not down_package_values:
            return

        assert isinstance(down_package_values, dict)
        option_values = PackageOptionValues()
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

        self._package_options.propagate_upstream(option_values, down_ref, own_ref,
                                                 pattern_options=pattern_options)

        # Upstream propagation to deps
        for name, option_values in sorted(list(down_package_values.items())):
            if name != own_ref.name:
                pkg_values = self._deps_package_values.setdefault(name, PackageOptionValues())
                pkg_values.propagate_upstream(option_values, down_ref, own_ref, name)

    def initialize_upstream(self, user_values, name=None):
        """ used to propagate from downstream the options to the upper requirements
        """
        if user_values is not None:
            assert isinstance(user_values, OptionsValues)
            # This code is necessary to process patterns like *:shared=True
            # To apply to the current consumer, which might not have name
            for pattern, pkg_options in sorted(user_values._reqs_options.items()):
                if fnmatch.fnmatch(name or "", pattern):
                    self._package_options.initialize_patterns(pkg_options)
            # Then, the normal assignment of values, which could override patterns
            self._package_options.values = user_values._package_values
            for package_name, package_values in user_values._reqs_options.items():
                pkg_values = self._deps_package_values.setdefault(package_name,
                                                                  PackageOptionValues())
                pkg_values.update(package_values)

    def validate(self):
        return self._package_options.validate()

    def propagate_downstream(self, ref, options):
        assert isinstance(options, OptionsValues)
        self._deps_package_values[ref.name] = options._package_values
        for k, v in options._reqs_options.items():
            self._deps_package_values[k] = v.copy()

    def clear_unused(self, prefs):
        """ remove all options not related to the passed references,
        that should be the upstream requirements
        """
        existing_names = [pref.ref.name for pref in prefs]
        self._deps_package_values = {k: v for k, v in self._deps_package_values.items()
                                     if k in existing_names}
