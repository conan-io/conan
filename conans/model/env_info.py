from collections import OrderedDict
from conans.util.log import logger
import os
import re


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

        # With vars if its setted the keep the setted value
        for varname, value in dep_env_info.vars.items():
            if varname not in self.vars:
                self.vars[varname] = value
            elif isinstance(self.vars[varname], list):
                if isinstance(value, list):
                    self.vars[varname].extend(value)
                else:
                    self.vars[varname].append(value)
            else:
                logger.warn("DISCARDED variable %s=%s from %s" % (varname, value, str(conan_ref)))
