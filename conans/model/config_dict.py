from conans.errors import ConanException
import yaml
from conans.model.values import Values


def bad_value_msg(name, value, value_range):
    return ("'%s' is not a valid '%s' value.\nPossible values are %s"
                                 % (value, name, value_range))


def undefined_field(name, field, fields=None, value=None):
    value_str = " for '%s'" % value if value else ""
    result = ["'%s.%s' doesn't exist%s" % (name, field, value_str)]
    result.append("'%s' possible configurations are %s" % (name, fields or "none"))
    return "\n".join(result)


def undefined_value(name):
    return "'%s' value not defined" % name


class ConfigItem(object):
    def __init__(self, definition, name, cls):
        self._name = name
        self._value = None
        self._cls = cls
        self._definition = {}
        if isinstance(definition, dict):
            # recursive
            for k, v in definition.items():
                k = str(k)
                self._definition[k] = cls(v, name, k)
        else:
            # list or tuple of possible values
            self._definition = sorted([str(v) for v in definition])

    def copy(self):
        """ deepcopy, recursive
        """
        cls = type(self)
        result = cls({}, name=self._name, cls=self._cls)
        result._value = self._value
        if self.is_final:
            result._definition = self._definition[:]
        else:
            result._definition = {k: v.copy() for k, v in self._definition.items()}
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
        return self._value

    def __eq__(self, other):
        if other is None:
            return self._value is None
        other = str(other)
        if other not in self.values_range:
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
            else:
                if v in self._definition:
                    self._definition.remove(v)
            if self._value == v:
                raise ConanException(bad_value_msg(self._name, v, self.values_range))

    def _get_child(self, item):
        if not isinstance(self._definition, dict):
            raise ConanException(undefined_field(self._name, item, None, self._value))
        if self._value is None:
            raise ConanException(undefined_value(self._name))
        return self._definition[self._value]

    def __getattr__(self, item):
        item = str(item)
        sub_config_dict = self._get_child(item)
        return getattr(sub_config_dict, item)

    def __setattr__(self, item, value):
        if item[0] == "_" or item.startswith("value"):
            return super(ConfigItem, self).__setattr__(item, value)

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
        if v not in self._definition:
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
        if self._value is None:
            raise ConanException(undefined_value(self._name))

        if isinstance(self._definition, dict):
            self._definition[self._value].validate()


class ConfigDict(object):
    def __init__(self, definition, name, parent_value=None):
        self._name = name  # settings, settings.compiler
        self._parent_value = parent_value  # gcc, x86
        cls = type(self)
        self._data = {str(k): ConfigItem(v, "%s.%s" % (name, k), cls)
                      for k, v in definition.items()}

    def copy(self):
        """ deepcopy, recursive
        """
        cls = type(self)
        result = cls({}, name=self._name, parent_value=self._parent_value)
        for k, v in self._data.items():
            result._data[k] = v.copy()
        return result

    @classmethod
    def loads(cls, text):
        name = cls.__name__.lower()
        if name == "packageoptions":
            name = "options"
        return cls(yaml.load(text) or {})

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
            raise ConanException(undefined_field(self._name, field, self.fields,
                                                 self._parent_value))

    def __getattr__(self, field):
        assert field[0] != "_", "ERROR %s" % field
        self._check_field(field)
        return self._data[field]

    def __setattr__(self, field, value):
        if field[0] == "_" or field.startswith("values"):
            return super(ConfigDict, self).__setattr__(field, value)

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
