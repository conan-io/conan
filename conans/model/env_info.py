from collections import OrderedDict
from conans.util.log import logger


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
        else:
            if not self._values_.get(name):
                self._values_[name] = []
            elif not isinstance(self._values_[name], list):
                tmp = self._values_[name]
                self._values_[name] = [tmp]
            return self._values_[name]

    def __setattr__(self, name, value):
        if (name.startswith("_") and name.endswith("_")):
            super(EnvInfo, self).__setattr__(name, value)
        else:
            self._values_[name] = value
        return

    @property
    def vars(self):
        return self._values_


class DepsEnvInfo(EnvInfo):
    """ All the env info for a conanfile dependencies
    """
    def __init__(self):
        super(DepsEnvInfo, self).__init__()
        self._dependencies_ = OrderedDict()

    @property
    def dependencies(self):
        return self._dependencies_.items()

    @property
    def deps(self):
        return self._dependencies_.keys()

    def __getitem__(self, item):
        return self._dependencies_[item]

    def update(self, dep_env_info, conan_ref=None):
        if conan_ref is not None:
            self._dependencies_[conan_ref.name] = dep_env_info
        else:
            self._dependencies_.update(dep_env_info.dependencies)

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
