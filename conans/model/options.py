
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


<<<<<<< HEAD
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

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        return self._dict == other._dict

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
        assert isinstance(option_text, str)
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
        result = ["[options]"]
        for name, value in self.items():
            # It is important to discard None values, so migrations in settings can be done
            # without breaking all existing packages SHAs, by adding a first "None" option
            # that doesn't change the final sha
            if value:
                result.append("%s=%s" % (name, value))
        return '\n'.join(result)


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
            v = v.strip() if isinstance(v, str) else v
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

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if not self._package_values == other._package_values:
            return False
        # It is possible that the entry in the dict is not defined
        for key, pkg_values in self._reqs_options.items():
            other_values = other[key]
            if not pkg_values == other_values:
                return False
        return True

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
        items = self.as_list()
        if items:
            result = []
            for key, value in items:
                if value is None or value == "None":
                    continue
                result.append("%s=%s" % (key, value))
            result.append("")
            return "\n".join(result)
        return ""

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
        #for key in sorted(list(self._reqs_options.keys())):
        #    result.append(self._reqs_options[key].sha)
        return '\n'.join(result)

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
=======
class _PackageOption:
    def __init__(self, name, value, possible_values=None):
>>>>>>> develop2
        self._name = name
        self._value = value  # Value None = not defined
        # possible_values only possible origin is recipes
        if possible_values is None or possible_values == "ANY":
            self._possible_values = None
        else:
            self._possible_values = [str(v) if v is not None else None for v in possible_values]

    def copy_conaninfo_option(self):
        # To generate a copy without validation, for package_id info.options value
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
        if other is None:
            return self._value is None
        other = str(other)
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
            raise ConanException("'%s' value not defined" % self._name)


class _PackageOptions:
    def __init__(self, recipe_options_definition=None):
        if recipe_options_definition is None:
            self._constrained = False
            self._data = {}
        else:
            self._constrained = True
            self._data = {str(option): _PackageOption(str(option), None, possible_values)
                          for option, possible_values in recipe_options_definition.items()}
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

    def copy_conaninfo_options(self):
        # To generate a copy without validation, for package_id info.options value
        result = _PackageOptions()
        for k, v in self._data.items():
            result._data[k] = v.copy_conaninfo_option()
        return result

    @property
    def fields(self):
        return sorted(list(self._data.keys()))

    def _ensure_exists(self, field):
        if self._constrained and field not in self._data:
            raise ConanException(option_not_exist_msg(field, list(self._data.keys())))

    def __getattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        try:
            return self._data[field]
        except KeyError:
            raise ConanException(option_not_exist_msg(field, list(self._data.keys())))

    def __delattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        if self._freeze:
            raise ConanException(f"Incorrect attempt to modify options '{field}'")
        self._ensure_exists(field)
        del self._data[field]

    def __setattr__(self, field, value):
        if field[0] == "_":
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

    def __init__(self, options=None, options_values=None):
        # options=None means an unconstrained/profile definition
        try:
            self._package_options = _PackageOptions(options)
            # Addressed only by name, as only 1 configuration is allowed
            # if more than 1 is present, 1 should be "private" requirement and its options
            # are not public, not overridable
            self._deps_package_options = {}  # {name("Boost": PackageOptions}
            if options_values:
                for k, v in options_values.items():
                    if v is None:
                        continue  # defining a None value means same as not giving value
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

    def __repr__(self):
        return self.dumps()

    def dumps(self):
        """ produces a multiline text representation of all values, first self then others.
        In alphabetical order, skipping real None (not string "None") values:
            option1=value1
            other_option=3
            OtherPack:opt3=12.1
        """
        result = ["%s=%s" % (k, v) for k, v in self._package_options.items() if v is not None]
        for pkg_pattern, pkg_option in sorted(self._deps_package_options.items()):
            for key, value in pkg_option.items():
                if value is not None:
                    result.append("%s:%s=%s" % (pkg_pattern, key, value))
        return "\n".join(result)

    @staticmethod
    def loads(text):
        """ parses a multiline text in the form produced by dumps(), NO validation here
        """
        values = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, value = line.split("=", 1)
            values[name] = value
        return Options(options_values=values)

    def serialize(self):
        # used by ConanInfo serialization, involved in "list package-ids" output
        # we need to maintain the "options" and "req_options" first level or servers will break
        # This happens always after reading from conaninfo.txt => all str and not None
        result = {k: v for k, v in self._package_options.items()}
        # Include the dependencies ones, in case they have been explicitly added in package_id()
        # to the conaninfo.txt, we want to report them
        for pkg_pattern, pkg_option in sorted(self._deps_package_options.items()):
            for key, value in pkg_option.items():
                result["%s:%s" % (pkg_pattern, key)] = value
        return {"options": result}

    def clear(self):
        # for header_only() clearing
        self._package_options.clear()
        self._deps_package_options.clear()

    def __contains__(self, option):
        return option in self._package_options

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

    def __getitem__(self, item):
        # To access dependencies options like ``options["mydep"]``. This will no longer be
        # a read case, only for defining values. Read access will be via self.dependencies["dep"]
        return self._deps_package_options.setdefault(item, _PackageOptions())

    def scope(self, name):
        """ when there are free options like "shared=True", they apply to the "consumer" package
        Once we know the name of such consumer package, it can be defined in the data, so it will
        be later correctly apply when processing options """
        package_options = self._deps_package_options.setdefault(name, _PackageOptions())
        package_options.update_options(self._package_options)
        self._package_options = _PackageOptions()

    def copy_conaninfo_options(self):
        # To generate the package_id info.options copy, that can destroy, change and remove things
        result = Options()
        result._package_options = self._package_options.copy_conaninfo_options()
        # In most scenarios this should be empty at this stage, because it was cleared
        for pkg_pattern, pkg_option in sorted(self._deps_package_options.items()):
            result._deps_package_options[pkg_pattern] = pkg_option.copy_conaninfo_options()
        return result

    def update_options(self, other):
        """
        dict-like update of options, "other" has priority, overwrite existing
        @type other: Options
        """
        self._package_options.update_options(other._package_options)
        for pkg, pkg_option in other._deps_package_options.items():
            self._deps_package_options.setdefault(pkg, _PackageOptions()).update_options(pkg_option)

    def apply_downstream(self, down_options, profile_options, own_ref):
        """ compute the current package options, starting from the self defined ones and applying
        the options defined by the downstrream consumers and the profile
        Only modifies the current package_options, not the dependencies ones
        """
        assert isinstance(down_options, Options)
        assert isinstance(profile_options, Options)

        for defined_options in down_options, profile_options:
            if own_ref is None or own_ref.name is None:
                # If the current package doesn't have a name defined, is a pure consumer without name
                # Get the non-scoped options, plus the "all-matching=*" pattern
                self._package_options.update_options(defined_options._package_options)
                for pattern, options in defined_options._deps_package_options.items():
                    if pattern == "*":
                        self._package_options.update_options(options, is_pattern=True)
            else:
                # If the current package has a name, there should be a match, either exact name
                # match, or a fnmatch approximate one
                for pattern, options in defined_options._deps_package_options.items():
                    if pattern == own_ref.name:  # exact match
                        self._package_options.update_options(options)
                    elif fnmatch.fnmatch(own_ref.name, pattern):  # approx match
                        self._package_options.update_options(options, is_pattern=True)
        self._package_options.freeze()

    def get_upstream_options(self, down_options, own_ref):
        """ compute which options should be propagated to the dependencies, a combination of the
        downstream defined default_options with the current default_options ones. This happens
        at "configure()" time, while building the graph. Also compute the minimum "self_options"
        which is the state that a package should define in order to reproduce
        """
        assert isinstance(down_options, Options)
        # self_options are the minimal necessary for a build-order
        # TODO: check this, isn't this just a copy?
        self_options = Options()
        for pattern, options in down_options._deps_package_options.items():
            self_options._deps_package_options.setdefault(pattern,
                                                          _PackageOptions()).update_options(options)

        # compute now the necessary to propagate all down - self + self deps
        upstream_options = Options()
        for pattern, options in down_options._deps_package_options.items():
            if pattern == own_ref.name:
                # Remove the exact match to this package, don't further propagate up
                continue
            self._deps_package_options.setdefault(pattern, _PackageOptions()).update_options(options)

        upstream_options._deps_package_options = self._deps_package_options
        # When the upstream is computed, the current dependencies are invalidated, so users will
        # not be able to do ``self.options["mydep"]`` because it will be empty. self.dependencies
        # is the way to access dependencies (in other methods)
        self._deps_package_options = {}
        return self_options, upstream_options

    def validate(self):
        # Check that all options have a value defined
        return self._package_options.validate()

    @property
    def sha(self):
        result = ["[options]"]
        d = self.dumps()
        if d:
            result.append(d)
        return '\n'.join(result)
