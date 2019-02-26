import yaml

from conans.errors import ConanException
from conans.model.values import Values


def bad_value_msg(name, value, value_range):
    tip = ""
    if "settings" in name:
        tip = '\nRead "http://docs.conan.io/en/latest/faq/troubleshooting.html' \
              '#error-invalid-setting"'

    return ("Invalid setting '%s' is not a valid '%s' value.\nPossible values are %s%s"
            % (value, name, value_range, tip))


def undefined_field(name, field, fields=None, value=None):
    value_str = " for '%s'" % value if value else ""
    result = ["'%s.%s' doesn't exist%s" % (name, field, value_str),
              "'%s' possible configurations are %s" % (name, fields or "none")]
    return ConanException("\n".join(result))


def undefined_value(name):
    return ConanException("'%s' value not defined" % name)


class SettingsItem(object):
    """ represents a setting value and its child info, which could be:
    - A range of valid values: [Debug, Release] (for settings.compiler.runtime of VS)
    - "ANY", as string to accept any value
    - A dict {subsetting: definition}, e.g. {version: [], runtime: []} for VS
    """
    def __init__(self, definition, name):
        self._name = name  # settings.compiler
        self._value = None  # gcc
        if isinstance(definition, dict):
            self._definition = {}
            # recursive
            for k, v in definition.items():
                k = str(k)
                self._definition[k] = Settings(v, name, k)
        elif definition == "ANY":
            self._definition = "ANY"
        else:
            # list or tuple of possible values
            self._definition = sorted(str(v) for v in definition)

    def __contains__(self, value):
        return value in (self._value or "")

    def copy(self):
        """ deepcopy, recursive
        """
        result = SettingsItem({}, name=self._name)
        result._value = self._value
        if self.is_final:
            result._definition = self._definition[:]
        else:
            result._definition = {k: v.copy() for k, v in self._definition.items()}
        return result

    def copy_values(self):
        if self._value is None and "None" not in self._definition:
            return None

        result = SettingsItem({}, name=self._name)
        result._value = self._value
        if self.is_final:
            result._definition = self._definition[:]
        else:
            result._definition = {k: v.copy_values() for k, v in self._definition.items()}
        return result

    @property
    def is_final(self):
        return not isinstance(self._definition, dict)

    def __bool__(self):
        if not self._value:
            return False
        return self._value.lower() not in ["false", "none", "0", "off"]

    def __nonzero__(self):
        return self.__bool__()

    def __str__(self):
        return str(self._value)

    def __eq__(self, other):
        if other is None:
            return self._value is None
        other = str(other)
        if self._definition != "ANY" and other not in self.values_range:
            raise ConanException(bad_value_msg(self._name, other, self.values_range))
        return other == self.__str__()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __delattr__(self, item):
        """ This is necessary to remove libcxx subsetting from compiler in config()
           del self.settings.compiler.stdlib
        """
        try:
            self._get_child(self._value).remove(item)
        except:
            pass

    def remove(self, values):
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        for v in values:
            v = str(v)
            if isinstance(self._definition, dict):
                self._definition.pop(v, None)
            elif self._definition != "ANY":
                if v in self._definition:
                    self._definition.remove(v)
        if self._value is not None and self._value not in self._definition:
            raise ConanException(bad_value_msg(self._name, self._value, self.values_range))

    def _get_child(self, item):
        if not isinstance(self._definition, dict):
            raise undefined_field(self._name, item, None, self._value)
        if self._value is None:
            raise undefined_value(self._name)
        return self._definition[self._value]

    def __getattr__(self, item):
        item = str(item)
        sub_config_dict = self._get_child(item)
        return getattr(sub_config_dict, item)

    def __setattr__(self, item, value):
        if item[0] == "_" or item.startswith("value"):
            return super(SettingsItem, self).__setattr__(item, value)

        item = str(item)
        sub_config_dict = self._get_child(item)
        return setattr(sub_config_dict, item, value)

    def __getitem__(self, value):
        value = str(value)
        try:
            return self._definition[value]
        except:
            raise ConanException(bad_value_msg(self._name, value, self.values_range))

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = str(v)
        if self._definition != "ANY" and v not in self._definition:
            raise ConanException(bad_value_msg(self._name, v, self.values_range))
        self._value = v

    @property
    def values_range(self):
        try:
            return sorted(list(self._definition.keys()))
        except:
            return self._definition

    @property
    def values_list(self):
        if self._value is None:
            return []
        result = []
        partial_name = ".".join(self._name.split(".")[1:])
        result.append((partial_name, self._value))
        if isinstance(self._definition, dict):
            sub_config_dict = self._definition[self._value]
            result.extend(sub_config_dict.values_list)
        return result

    def validate(self):
        if self._value is None and "None" not in self._definition:
            raise undefined_value(self._name)

        if isinstance(self._definition, dict):
            key = "None" if self._value is None else self._value
            self._definition[key].validate()


class Settings(object):
    def __init__(self, definition=None, name="settings", parent_value=None):
        if parent_value == "None" and definition:
            raise ConanException("settings.yml: None setting can't have subsettings")
        definition = definition or {}
        self._name = name  # settings, settings.compiler
        self._parent_value = parent_value  # gcc, x86
        self._data = {str(k): SettingsItem(v, "%s.%s" % (name, k))
                      for k, v in definition.items()}

    def get_safe(self, name):
        try:
            tmp = self
            for prop in name.split("."):
                tmp = getattr(tmp, prop, None)
        except ConanException:
            return None
        if tmp is not None and tmp.value and tmp.value != "None":  # In case of subsettings is None
            return str(tmp)
        return None

    def copy(self):
        """ deepcopy, recursive
        """
        result = Settings({}, name=self._name, parent_value=self._parent_value)
        for k, v in self._data.items():
            result._data[k] = v.copy()
        return result

    def copy_values(self):
        """ deepcopy, recursive
        """
        result = Settings({}, name=self._name, parent_value=self._parent_value)
        for k, v in self._data.items():
            value = v.copy_values()
            if value is not None:
                result._data[k] = value
        return result

    @staticmethod
    def loads(text):
        return Settings(yaml.safe_load(text) or {})

    def validate(self):
        for field in self.fields:
            child = self._data[field]
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
            raise undefined_field(self._name, field, self.fields, self._parent_value)

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
            return super(Settings, self).__setattr__(field, value)

        self._check_field(field)
        self._data[field].value = value

    @property
    def values(self):
        return Values.from_list(self.values_list)

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
        assert isinstance(vals, Values)
        self.values_list = vals.as_list()

    def constraint(self, constraint_def):
        """ allows to restrict a given Settings object with the input of another Settings object
        1. The other Settings object MUST be exclusively a subset of the former.
           No additions allowed
        2. If the other defines {"compiler": None} means to keep the full specification
        """
        if isinstance(constraint_def, (list, tuple, set)):
            constraint_def = {str(k): None for k in constraint_def or []}
        else:
            constraint_def = {str(k): v for k, v in constraint_def.items()}

        fields_to_remove = []
        for field, config_item in self._data.items():
            if field not in constraint_def:
                fields_to_remove.append(field)
                continue

            other_field_def = constraint_def[field]
            if other_field_def is None:  # Means leave it as is
                continue
            if isinstance(other_field_def, str):
                other_field_def = [other_field_def]

            values_to_remove = []
            for value in config_item.values_range:  # value = "Visual Studio"
                if value not in other_field_def:
                    values_to_remove.append(value)
                else:  # recursion
                    if (not config_item.is_final and isinstance(other_field_def, dict) and
                            other_field_def[value] is not None):
                        config_item[value].constraint(other_field_def[value])

            # Sanity check of input constraint values
            for value in other_field_def:
                if value not in config_item.values_range:
                    raise ConanException(bad_value_msg(field, value, config_item.values_range))

            config_item.remove(values_to_remove)

        # Sanity check for input constraint wrong fields
        for field in constraint_def:
            if field not in self._data:
                raise undefined_field(self._name, field, self.fields)

        # remove settings not defined in the constraint
        self.remove(fields_to_remove)
