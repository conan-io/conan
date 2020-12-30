import fnmatch
from collections import OrderedDict

from conans.errors import ConanException


class _ConfModule(object):
    def __init__(self):
        self._confs = {}  # Component => dict {config-name: value}

    def __getattr__(self, item):
        return self._confs.get(item)

    def update(self, other):
        """
        :type other: _ConfModule
        """
        self._confs.update(other._confs)

    def set_value(self, k, v):
        self._confs[k] = v

    def __repr__(self):
        return "_ConfModule: " + repr(self._confs)

    def items(self):
        return self._confs.items()


def _is_profile_module(module_name):
    # These are the modules that are propagated to profiles and user recipes
    _user_modules = "tools.", "user."
    return any(module_name.startswith(user_module) for user_module in _user_modules)


class Conf(object):

    def __init__(self):
        self._conf_modules = {}  # module_name => _ConfModule

    def __getitem__(self, module_name):
        return self._conf_modules.get(module_name, _ConfModule())

    def __repr__(self):
        return "Conf: " + repr(self._conf_modules)

    def items(self):
        return self._conf_modules.items()

    def filter_user_modules(self):
        result = Conf()
        for k, v in self._conf_modules.items():
            if _is_profile_module(k):
                result._conf_modules[k] = v
        return result

    def update(self, other):
        """
        :type other: Conf
        """
        for module_name, module_conf in other._conf_modules.items():
            existing = self._conf_modules.get(module_name)
            if existing:
                existing.update(module_conf)
            else:
                self._conf_modules[module_name] = module_conf

    def set_value(self, module_name, k, v):
        self._conf_modules.setdefault(module_name, _ConfModule()).set_value(k, v)


class ConfDefinition(object):
    def __init__(self):
        self._pattern_confs = OrderedDict()  # pattern (including None) => Conf

    def __bool__(self):
        return bool(self._pattern_confs)

    def __repr__(self):
        return "ConfDefinition: " + repr(self._pattern_confs)

    __nonzero__ = __bool__

    def __getitem__(self, module_name):
        """ if a module name is requested for this, always goes to the None-Global config
        """
        return self._pattern_confs.get(None, Conf())[module_name]

    def get_conanfile_conf(self, name):
        result = Conf()
        for pattern, conf in self._pattern_confs.items():
            # TODO: standardize this package-pattern matching
            if pattern is None or fnmatch.fnmatch(name, pattern):
                result.update(conf)
        return result

    def update_conf_definition(self, other):
        """
        This is used for composition of profiles [conf] section
        :type other: ConfDefinition
        """
        for k, v in other._pattern_confs.items():
            existing = self._pattern_confs.get(k)
            if existing:
                existing.update(v)
            else:
                self._pattern_confs[k] = v

    def rebase_conf_definition(self, other):
        """
        for taking the new conan_conf.txt and composing with the profile [conf]
        :type other: ConfDefinition
        """
        for k, v in other._pattern_confs.items():
            new_v = v.filter_user_modules()  # Creates a copy, filtered
            existing = self._pattern_confs.get(k)
            if existing:
                new_v.update(existing)
            self._pattern_confs[k] = new_v

    def dumps(self):
        result = []
        for pattern, conf in self._pattern_confs.items():
            for name, values in conf.items():
                for k, v in values.items():
                    if pattern:
                        result.append("{}:{}:{}={}".format(pattern, name, k, v))
                    else:
                        result.append("{}:{}={}".format(name, k, v))
        return "\n".join(result)

    def loads(self, text, profile=False):
        self._pattern_confs = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            left, value = line.split("=", 1)
            tokens = left.split(":", 2)
            if len(tokens) == 3:
                pattern, conf_module, name = tokens
            else:
                assert len(tokens) == 2
                conf_module, name = tokens
                pattern = None
            if not _is_profile_module(conf_module):
                if profile:
                    raise ConanException("[conf] '{}' not allowed in profiles".format(line))
                if pattern is not None:
                    raise ConanException("Conf '{}' cannot have a package pattern".format(line))
            conf = self._pattern_confs.setdefault(pattern, Conf())
            conf.set_value(conf_module, name, value)
