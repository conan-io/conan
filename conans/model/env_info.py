import os
import re
from collections import OrderedDict

from conans.util.log import logger


class EnvValues(object):
    """ Object to represent the introduced env values entered by the user
    with the -e or profiles etc.
        self._data is a dictionary with: {(package, var): value}. "package" can be None if the var is global.
    """

    def __init__(self):
        self._data = {}

    @staticmethod
    def loads(text):
        ret = EnvValues()
        for env_def in text.splitlines():
            try:
                tmp = env_def.split("=", 1)
                name = tmp[0]
                value = tmp[1].strip()
                package = None
                if ":" in name:
                    tmp = name.split(":", 1)
                    package = tmp[0].strip()
                    name = tmp[1].strip()
                else:
                    name = name.strip()
                ret.add(name, value, package)
            except Exception:
                pass
        return ret

    def dumps(self):
        result = []
        for (name, value) in sorted(self._global_values()):
            result.append("%s=%s" % (name, value))
        for (name, value) in sorted(self._all_package_values()):
            result.append("%s=%s" % (name, value))
        return "\n".join(result)

    @property
    def data(self):
        return self._data

    @property
    def _sorted_data(self):
        # Python 3 can't compare None with strings, so if None we order just with the var name
        return sorted(self._data.items(), key=lambda x: "%s_%s" % x if x[0] else x[1])

    def add(self, name, value, package=None):
        # It prioritizes the data already introduced
        if (package, name) not in self._data:
            self._data[(package, name)] = value

    def _global_values(self):
        """return [(name, value), (name, value)] for global env variables"""
        return [(name, value) for (pname, name), value in self._sorted_data
                if pname is None]

    def _package_values(self, package):
        """return the environment variables that apply for a given package name:
        [(name, value), (name, value)] for the specified package"""
        assert(package is not None)
        return [(name, value) for (pname, name), value in self._sorted_data
                if pname == package]

    def _all_package_values(self):
        return sorted([("%s:%s" % (pname, name), value) for (pname, name), value in self.data.items()
                       if pname])

    def update(self, env_obj):
        """accepts other EnvValues object or DepsEnvInfo
           it prioritize the values that are already at self._data
        """
        if env_obj:
            if isinstance(env_obj, EnvValues):
                for (package_name, name), value in env_obj._data.items():
                    self.add(name, value, package_name)
            else:  # DepsEnvInfo. the OLD values are always kept, never overwrite,
                for (name, value) in env_obj.vars.items():
                    name = name.upper() if name.lower() == "path" else name
                    if isinstance(value, list):
                        # Append to OLD value, not overwrite it.
                        value = os.pathsep.join(value)
                        if (None, name) in self._data:
                            self._data[(None, name)] = '%s%s%s' % (self._data[(None, name)],
                                                                   os.pathsep, value)
                        else:
                            self.add(name, value)
                    else:
                        self.add(name, value)

    def env_dict(self, package_name):
        """Returns a dict of env variables that applies to package 'name' """
        ret = {}
        ret.update(dict(self._global_values()))
        # Scoped variables are prioritized over the global ones
        if package_name:
            ret.update(self._package_values(package_name))
        return ret

    def __repr__(self, *args, **kwargs):
        return str(self._global_values()) + str(self._all_package_values())


class EnvInfo(object):
    """ Object that stores all the environment variables required:

    env = EnvInfo()
    env.hola = True
    env.Cosa.append("OTRO")
    env.Cosa.append("MAS")
    env.Cosa = "hello"
    env.Cosa.append("HOLA")

    """
    def __init__(self, root_folder=None):
        self._root_folder_ = root_folder
        self._values_ = {}

    def __getattr__(self, name):
        if name.startswith("_") and name.endswith("_"):
            return super(EnvInfo, self).__getattr__(name)

        attr = self._values_.get(name)
        if not attr:
            self._values_[name] = []
        elif not isinstance(attr, list):
            self._values_[name] = [attr]
        return self._values_[name]

    def __setattr__(self, name, value):
        if (name.startswith("_") and name.endswith("_")):
            return super(EnvInfo, self).__setattr__(name, value)
        self._values_[name] = value

    @property
    def vars(self):
        return self._values_


class DepsEnvInfo(EnvInfo):
    """ All the env info for a conanfile dependencies
    """
    def __init__(self):
        super(DepsEnvInfo, self).__init__()
        self._dependencies_ = OrderedDict()

    def dumps(self):
        result = []

        for var, values in self.vars.items():
            result.append("[%s]" % var)
            result.extend(values)
        result.append("")

        for name, env_info in self._dependencies_.items():
            for var, values in env_info.vars.items():
                result.append("[%s:%s]" % (name, var))
                result.extend(values)
            result.append("")

        return os.linesep.join(result)

    @staticmethod
    def loads(text):
        pattern = re.compile("^\[([a-zA-Z0-9_:-]+)\]([^\[]+)", re.MULTILINE)
        result = DepsEnvInfo()

        for m in pattern.finditer(text):
            var_name = m.group(1)
            lines = [line.strip() for line in m.group(2).splitlines() if line.strip()]
            tokens = var_name.split(":")
            if len(tokens) == 2:
                library = tokens[0]
                var_name = tokens[1]
                result._dependencies_.setdefault(library, EnvInfo()).vars[var_name] = lines
            else:
                result.vars[var_name] = lines

        return result

    @property
    def dependencies(self):
        return self._dependencies_.items()

    @property
    def deps(self):
        return self._dependencies_.keys()

    def __getitem__(self, item):
        return self._dependencies_[item]

    def update(self, dep_env_info, conan_ref):
        self._dependencies_[conan_ref.name] = dep_env_info

        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        # With vars if its setted the keep the setted value
        for varname, value in dep_env_info.vars.items():
            if varname not in self.vars:
                self.vars[varname] = value
            elif isinstance(self.vars[varname], list):
                if isinstance(value, list):
                    self.vars[varname] = merge_lists(self.vars[varname], value)
                else:
                    self.vars[varname] = merge_lists(self.vars[varname], [value])
            else:
                logger.warn("DISCARDED variable %s=%s from %s" % (varname, value, str(conan_ref)))
