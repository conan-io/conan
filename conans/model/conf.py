import fnmatch
from collections import OrderedDict


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


class Conf(object):
    def __init__(self):
        self._conf_modules = {}  # module_name => _ConfModule

    def __getitem__(self, module_name):
        return self._conf_modules.get(module_name, _ConfModule())

    def __repr__(self):
        return "Conf: " + repr(self._conf_modules)

    def items(self):
        return self._conf_modules.items()

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

    __nonzero__ = __bool__

    def get_conanfile_conf(self, name):
        result = Conf()
        for pattern, conf in self._pattern_confs.items():
            # TODO: standardize this package-pattern matching
            if pattern is None or fnmatch.fnmatch(name, pattern):
                result.update(conf)
        return result

    def update(self, other):
        """
        :type other: ConfDefinition
        """
        for k, v in other._pattern_confs.items():
            existing = self._pattern_confs.get(k)
            if existing:
                existing.update(v)
            else:
                self._pattern_confs[k] = v

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

    def loads(self, text):
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
            conf = self._pattern_confs.setdefault(pattern, Conf())
            conf.set_value(conf_module, name, value)
