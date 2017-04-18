from conans.util.sha import sha1
from conans.errors import ConanException


class Values(object):
    def __init__(self, value="values"):
        self._value = str(value)
        self._dict = {}  # {key: Values()}
        self._modified = {}  # {"compiler.version.arch": (old_value, old_reference)}

    def __getattr__(self, attr):
        if attr not in self._dict:
            return None
        return self._dict[attr]

    def clear(self):
        # TODO: Test. DO not delete, might be used by package_id() to clear settings values
        self._dict.clear()
        self._value = ""

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            return super(Values, self).__setattr__(attr, value)
        self._dict[attr] = Values(value)

    def copy(self):
        """ deepcopy, recursive
        """
        result = Values(self._value)
        for k, v in self._dict.items():
            result._dict[k] = v.copy()
        return result

    @property
    def fields(self):
        """ return a sorted list of fields: [compiler, os, ...]
        """
        return sorted(list(self._dict.keys()))

    def __bool__(self):
        return self._value.lower() not in ["false", "none", "0", "off", ""]

    def __nonzero__(self):
        return self.__bool__()

    def __str__(self):
        return self._value

    def __eq__(self, other):
        return str(other) == self.__str__()

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def loads(cls, text):
        result = []
        for line in text.splitlines():
            if not line.strip():
                continue
            name, value = line.split("=")
            result.append((name.strip(), value.strip()))
        return cls.from_list(result)

    def as_list(self, list_all=True):
        result = []
        for field in self.fields:
            value = getattr(self, field)
            if value or list_all:
                result.append((field, str(value)))
                child_lines = value.as_list()
                for (child_name, child_value) in child_lines:
                    result.append(("%s.%s" % (field, child_name), child_value))
        return result

    @classmethod
    def from_list(cls, data):
        result = cls()
        for (field, value) in data:
            tokens = field.split(".")
            attr = result
            for token in tokens[:-1]:
                attr = getattr(attr, token)
                if attr is None:
                    raise ConanException("%s not defined for %s\n"
                                         "Please define %s value first too"
                                         % (token, field, token))
            setattr(attr, tokens[-1], Values(value))
        return result

    def dumps(self):
        """ produces a text string with lines containine a flattened version:
        compiler.arch = XX
        compiler.arch.speed = YY
        """
        return "\n".join(["%s=%s" % (field, value)
                          for (field, value) in self.as_list()])

    def serialize(self):
        return self.as_list()

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
