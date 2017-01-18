from conans.util.sha import sha1
from collections import defaultdict
from conans.errors import ConanException
import yaml
import six


_falsey_options = ["false", "none", "0", "off", ""]


class PackageValue(str):
    def __bool__(self):
        return self.lower() not in _falsey_options

    def __nonzero__(self):
        return self.__bool__()

    def __eq__(self, other):
        return str(other).__eq__(self)

    def __ne__(self, other):
        return not self.__eq__(other)


class PackageValues(object):
    def __init__(self):
        self._dict = {}  # {option_name: PackageValue}
        self._modified = {}

    def __getattr__(self, attr):
        if attr not in self._dict:
            return None
        return self._dict[attr]

    def clear(self):
        self._dict.clear()

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            return super(PackageValues, self).__setattr__(attr, value)
        self._dict[attr] = PackageValue(value)

    def copy(self):
        result = PackageValues()
        for k, v in self._dict.items():
            result._dict[k] = v
        return result

    @property
    def fields(self):
        """ return a sorted list of fields: [compiler, os, ...]
        """
        return sorted(list(self._dict.keys()))

    @staticmethod
    def loads(text):
        result = []
        for line in text.splitlines():
            if not line.strip():
                continue
            name, value = line.split("=")
            result.append((name.strip(), value.strip()))
        return PackageValues.from_list(result)

    def as_list(self, list_all=True):
        result = []
        for field in self.fields:
            value = self._dict[field]
            if value or list_all:
                result.append((field, str(value)))
        return result

    @staticmethod
    def from_list(data):
        result = PackageValues()
        for (field, value) in data:
            result._dict[field] = PackageValue(value)
        return result

    def add(self, option_text):
        assert isinstance(option_text, six.string_types)
        name, value = option_text.split("=")
        self._dict[name.strip()] = PackageValue(value.strip())

    def update(self, other):
        assert isinstance(other, PackageValues)
        self._dict.update(other._dict)

    def propagate_upstream(self, down_package_values, down_ref, own_ref, output, package_name):
        if not down_package_values:
            return

        assert isinstance(down_package_values, PackageValues)
        current_values = {k: v for (k, v) in self.as_list()}
        for (name, value) in down_package_values.as_list():
            current_value = current_values.get(name)
            if value == current_value:
                continue

            modified = self._modified.get(name)
            if modified is not None:
                modified_value, modified_ref = modified
                output.werror("%s tried to change %s option %s:%s to %s\n"
                              "but it was already assigned to %s by %s"
                              % (down_ref, own_ref, package_name, name, value,
                                 modified_value, modified_ref))
            else:
                self._modified[name] = (value, down_ref)
                self._dict[name] = value

    def dumps(self):
        """ produces a text string with lines containine a flattened version:
        compiler.arch = XX
        compiler.arch.speed = YY
        """
        return "\n".join(["%s=%s" % (field, value)
                          for (field, value) in self.as_list()])

    def serialize(self):
        return self.as_list()

    @staticmethod
    def deserialize(data):
        return PackageValues.from_list(data)

    @property
    def sha(self):
        result = []
        for (name, value) in self.as_list(list_all=False):
            # It is important to discard None values, so migrations in settings can be done
            # without breaking all existing packages SHAs, by adding a first "None" option
            # that doesn't change the final sha
            if value != "None":
                result.append("%s=%s" % (name, value))
        return sha1('\n'.join(result).encode())


def bad_value_msg(name, value, value_range):
    return ("'%s' is not a valid 'options.%s' value.\nPossible values are %s"
            % (value, name, value_range))


def undefined_option(option_name, existing_options):
    result = ["'options.%s' doesn't exist" % option_name]
    result.append("Possible options are %s" % existing_options or "none")
    return "\n".join(result)


def undefined_value(name):
    return "'%s' value not defined" % name


class PackageOption(object):
    def __init__(self, possible_values, name):
        self._name = name
        self._value = None
        if possible_values == "ANY":
            self._possible_values = "ANY"
        else:
            self._possible_values = sorted(str(v) for v in possible_values)

    def __bool__(self):
        if not self._value:
            return False
        return self._value.lower() not in _falsey_options

    def __nonzero__(self):
        return self.__bool__()

    def __str__(self):
        return self._value

    def __eq__(self, other):
        if other is None:
            return self._value is None
        other = str(other)
        if self._possible_values != "ANY" and other not in self._possible_values:
            raise ConanException(bad_value_msg(self._name, other, self._possible_values))
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

        if self._value is not None and self._value not in self._possible_values:
            raise ConanException(bad_value_msg(self._name, self._value, self._possible_values))

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = str(v)
        if self._possible_values != "ANY" and v not in self._possible_values:
            raise ConanException(bad_value_msg(self._name, v, self._possible_values))
        self._value = v

    @property
    def values_list(self):
        if self._value is None:
            return []
        result = []
        result.append((self._name, self._value))
        return result

    def validate(self):
        if self._value is None and "None" not in self._possible_values:
            raise ConanException(undefined_value(self._name))


class PackageOptions(object):
    def __init__(self, definition):
        definition = definition or {}
        self._data = {str(k): PackageOption(v, str(k))
                      for k, v in definition.items()}
        self._modified = {}

    def copy(self):
        raise Exception("BOOM cannot copy PackageOptions")
        result = PackageOptions({})
        for k, v in self._data.items():
            result._data[k] = v.copy()
        return result

    @staticmethod
    def loads(text):
        return PackageOptions(yaml.load(text) or {})

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

    def _check_field(self, field):
        if field not in self._data:
            raise ConanException(undefined_option(field, self.fields))

    def __getattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        self._check_field(field)
        return self._data[field]

    def __delattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        self._check_field(field)
        del self._data[field]

    def __setattr__(self, field, value):
        if field[0] == "_" or field.startswith("values"):
            return super(PackageOptions, self).__setattr__(field, value)

        self._check_field(field)
        self._data[field].value = value

    @property
    def values(self):
        return PackageValues.from_list(self.values_list)

    @property
    def values_list(self):
        result = []
        for field in self.fields:
            config_item = self._data[field]
            result.extend(config_item.values_list)
        return result

    def items(self):
        return self.values_list

    def iteritems(self):
        return self.values_list

    @values_list.setter
    def values_list(self, vals):
        """ receives a list of tuples (compiler.version, value)
        """
        assert isinstance(vals, list), vals
        for (name, value) in vals:
            list_settings = name.split(".")
            attr = self
            for setting in list_settings[:-1]:
                attr = getattr(attr, setting)
            setattr(attr, list_settings[-1], str(value))

    @values.setter
    def values(self, vals):
        assert isinstance(vals, PackageValues)
        self.values_list = vals.as_list()

    def propagate_upstream(self, values, down_ref, own_ref, output):
        """ update must be controlled, to not override lower
        projects options
        """
        if not values:
            return

        current_values = {k: v for (k, v) in self.values_list}
        for (name, value) in values.as_list():
            current_value = current_values.get(name)
            if value == current_value:
                continue

            modified = self._modified.get(name)
            if modified is not None:
                modified_value, modified_ref = modified
                if modified_value == value:
                    continue
                else:
                    output.werror("%s tried to change %s option %s to %s\n"
                                  "but it was already assigned to %s by %s"
                                  % (down_ref, own_ref, name, value, modified_value, modified_ref))
            else:
                self._modified[name] = (value, down_ref)
                list_settings = name.split(".")
                attr = self
                for setting in list_settings[:-1]:
                    attr = getattr(attr, setting)
                setattr(attr, list_settings[-1], str(value))


class Options(object):
    """ all options of a package, both its own options and the upstream
    ones.
    Owned by conanfile
    """
    def __init__(self, options):
        assert isinstance(options, PackageOptions)
        self._options = options
        # Addressed only by name, as only 1 configuration is allowed
        # if more than 1 is present, 1 should be "private" requirement and its options
        # are not public, not overridable
        self._reqs_options = {}  # {name("Boost": PackageValues}

    def clear(self):
        self._options.clear()

    def __getitem__(self, item):
        return self._reqs_options.setdefault(item, PackageValues())

    def __getattr__(self, attr):
        return getattr(self._options, attr)

    def __setattr__(self, attr, value):
        if attr[0] == "_" or attr == "values":
            return super(Options, self).__setattr__(attr, value)
        return setattr(self._options, attr, value)

    def __delattr__(self, field):
        try:
            self._options.__delattr__(field)
        except ConanException:
            pass

    @property
    def values(self):
        result = OptionsValues()
        result._options = PackageValues.from_list(self._options.values_list)
        for k, v in self._reqs_options.items():
            result._reqs_options[k] = v.copy()
        return result

    @values.setter
    def values(self, v):
        assert isinstance(v, OptionsValues)
        self._options.values = v._options
        self._reqs_options.clear()
        for k, v in v._reqs_options.items():
            self._reqs_options[k] = v.copy()

    def propagate_upstream(self, values, down_ref, own_ref, output):
        """ used to propagate from downstream the options to the upper requirements
        """
        if values is not None:
            assert isinstance(values, OptionsValues)
            own_values = values.pop(own_ref.name)
            self._options.propagate_upstream(own_values, down_ref, own_ref, output)
            for name, option_values in sorted(list(values._reqs_options.items())):
                self._reqs_options.setdefault(name, PackageValues()).propagate_upstream(option_values,
                                                                                 down_ref,
                                                                                 own_ref,
                                                                                 output,
                                                                                 name)

    def initialize_upstream(self, values, base_name=None):
        """ used to propagate from downstream the options to the upper requirements
        """
        if values is not None:
            assert isinstance(values, OptionsValues)
            package_options = values._reqs_options.pop(base_name, None)
            if package_options:
                values._options.update(package_options)
            self._options.values = values._options
            for name, option_values in values._reqs_options.items():
                self._reqs_options.setdefault(name, PackageValues()).update(option_values)

    def validate(self):
        return self._options.validate()

    def propagate_downstream(self, ref, options):
        assert isinstance(options, OptionsValues)
        self._reqs_options[ref.name] = options._options
        for k, v in options._reqs_options.items():
            self._reqs_options[k] = v.copy()

    def clear_unused(self, references):
        """ remove all options not related to the passed references,
        that should be the upstream requirements
        """
        existing_names = [r.conan.name for r in references]
        for name in list(self._reqs_options.keys()):
            if name not in existing_names:
                self._reqs_options.pop(name)


class OptionsValues(object):
    """ static= True,
    Boost.static = False,
    Poco.optimized = True
    """
    def __init__(self):
        self._options = PackageValues()
        self._reqs_options = {}  # {name("Boost": PackageValues}

    def __getitem__(self, item):
        return self._reqs_options.setdefault(item, PackageValues())

    def __setitem__(self, item, value):
        self._reqs_options[item] = value

    def pop(self, item):
        return self._reqs_options.pop(item, None)

    def __repr__(self):
        return self.dumps()

    def __getattr__(self, attr):
        return getattr(self._options, attr)

    def copy(self):
        result = OptionsValues()
        result._options = self._options.copy()
        for k, v in self._reqs_options.items():
            result._reqs_options[k] = v.copy()
        return result

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            return super(OptionsValues, self).__setattr__(attr, value)
        return setattr(self._options, attr, value)

    def clear_indirect(self):
        for v in self._reqs_options.values():
            v.clear()

    def as_list(self):
        result = []
        options_list = self._options.as_list()
        if options_list:
            result.extend(options_list)
        for key in sorted(self._reqs_options.keys()):
            for line in self._reqs_options[key].as_list():
                line_key, line_value = line
                result.append(("%s:%s" % (key, line_key), line_value))
        return result

    @staticmethod
    def from_list(data):
        result = OptionsValues()
        by_package = defaultdict(list)
        for k, v in data:
            tokens = k.split(":")
            if len(tokens) == 2:
                package, option = tokens
                by_package[package.strip()].append((option, v))
            else:
                by_package[None].append((k, v))
        result._options = PackageValues.from_list(by_package[None])
        for k, v in by_package.items():
            if k is not None:
                result._reqs_options[k] = PackageValues.from_list(v)
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
        result = OptionsValues()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # To avoid problems with values containing ":" as URLs
            name, value = line.split("=")
            tokens = name.split(":")
            if len(tokens) == 2:
                package, option = tokens
                current = result._reqs_options.setdefault(package.strip(), PackageValues())
            else:
                option = tokens[0].strip()
                current = result._options
            option = "%s=%s" % (option, value)
            current.add(option)
        return result

    def sha(self, non_dev_requirements):
        result = []
        result.append(self._options.sha)
        if non_dev_requirements is None:  # Not filtering
            for key in sorted(list(self._reqs_options.keys())):
                result.append(self._reqs_options[key].sha)
        else:
            for key in sorted(list(self._reqs_options.keys())):
                non_dev = key in non_dev_requirements
                if non_dev:
                    result.append(self._reqs_options[key].sha)
        return sha1('\n'.join(result).encode())

    def serialize(self):
        ret = {}
        ret["options"] = self._options.serialize()
        ret["req_options"] = {}
        for name, values in self._reqs_options.items():
            ret["req_options"][name] = values.serialize()
        return ret

    @staticmethod
    def deserialize(data):
        result = OptionsValues()
        result._options = PackageValues.deserialize(data["options"])
        for name, data_values in data["req_options"].items():
            result._reqs_options[name] = PackageValues.deserialize(data_values)
        return result
