import copy
import re
from collections import OrderedDict, defaultdict

from conans.errors import ConanException
from conans.util.log import logger


def unquote(text):
    text = text.strip()
    if len(text) > 1 and (text[0] == text[-1]) and text[0] in "'\"":
        return text[1:-1]
    return text


class EnvValues(object):
    """ Object to represent the introduced env values entered by the user
    with the -e or profiles etc.
        self._data is a dictionary with: {package: {var: value}}
            "package" can be None if the var is global.
            "value" can be a list or a string. If it's a list the variable is appendable like PATH or PYTHONPATH
    """

    def __init__(self):
        self._data = defaultdict(dict)

    def copy(self):
        ret = EnvValues()
        ret._data = copy.deepcopy(self._data)
        return ret

    @staticmethod
    def load_value(the_value):
        if the_value.startswith("[") and the_value.endswith("]"):
            return [val.strip() for val in the_value[1:-1].split(",") if val]
        else:
            return the_value

    @staticmethod
    def loads(text):
        ret = EnvValues()
        if not text:
            return ret
        for env_def in text.splitlines():
            try:
                if env_def:
                    if "=" not in env_def:
                        raise ConanException("Invalid env line '%s'" % env_def)
                    tmp = env_def.split("=", 1)
                    name = tmp[0]
                    value = unquote(tmp[1])
                    package = None
                    if ":" in name:
                        tmp = name.split(":", 1)
                        package = tmp[0].strip()
                        name = tmp[1].strip()
                    else:
                        name = name.strip()
                    # Lists values=> MYVAR=[1,2,three]
                    value = EnvValues.load_value(value)
                    ret.add(name, value, package)
            except ConanException:
                raise
            except Exception as exc:
                raise ConanException("Error parsing the env values: %s" % str(exc))

        return ret

    def dumps(self):

        def append_vars(pairs, result):
            for name, value in sorted(pairs.items()):
                if isinstance(value, list):
                    value = "[%s]" % ",".join(value)
                if package:
                    result.append("%s:%s=%s" % (package, name, value.replace("\\", "/")))
                else:
                    result.append("%s=%s" % (name, value.replace("\\", "/")))

        result = []
        # First the global vars
        for package, pairs in self._sorted_data:
            if package is None:
                append_vars(pairs, result)

        # Then the package scoped ones
        for package, pairs in self._sorted_data:
            if package is not None:
                append_vars(pairs, result)

        return "\n".join(result)

    @property
    def data(self):
        return self._data

    @property
    def _sorted_data(self):
        # Python 3 can't compare None with strings, so if None we order just with the var name
        return [(key, self._data[key]) for key in sorted(self._data, key=lambda x: x if x else "a")]

    def add(self, name, value, package=None):
        # New data, not previous value
        if name not in self._data[package]:
            if isinstance(value, list):
                self._data[package][name] = value
            else:
                self._data[package][name] = value.replace("\\", "/")
        # There is data already
        else:
            # Only append at the end if we had a list
            if isinstance(self._data[package][name], list):
                if isinstance(value, list):
                    self._data[package][name].extend(value)
                else:
                    self._data[package][name].append(value)

    def remove(self, name, package=None):
        del self._data[package][name]

    def update(self, env_obj):
        """accepts other EnvValues object or DepsEnvInfo
           it prioritize the values that are already at self._data
        """
        if env_obj:
            if isinstance(env_obj, EnvValues):
                for package_name, env_vars in env_obj.data.items():
                    for name, value in env_vars.items():
                        if isinstance(value, list):
                            value = copy.copy(value)  # Aware of copying by reference the list
                        self.add(name, value, package_name)
            # DepsEnvInfo. the OLD values are always kept, never overwrite,
            elif isinstance(env_obj, DepsEnvInfo):
                for (name, value) in env_obj.vars.items():
                    name = name.upper() if name.lower() == "path" else name
                    self.add(name, value)
            else:
                raise ConanException("unknown env type: %s" % env_obj)

    def env_dicts(self, package_name):
        """Returns two dicts of env variables that applies to package 'name',
         the first for simple values A=1, and the second for multiple A=1;2;3"""
        ret = {}
        ret_multi = {}
        # First process the global variables
        for package, pairs in self._sorted_data:
            for name, value in pairs.items():
                if package is None:
                    if isinstance(value, list):
                        ret_multi[name] = value
                    else:
                        ret[name] = value

        # Then the package scoped vars, that will override the globals
        for package, pairs in self._sorted_data:
            for name, value in pairs.items():
                if package == package_name:
                    if isinstance(value, list):
                        ret_multi[name] = value
                        if name in ret:  # Already exists a global variable, remove it
                            del ret[name]
                    else:
                        ret[name] = value
                        if name in ret_multi:  # Already exists a list global variable, remove it
                            del ret_multi[name]
        return ret, ret_multi

    def __repr__(self):
        return str(dict(self._data))


class EnvInfo(object):
    """ Object that stores all the environment variables required:

    env = EnvInfo()
    env.hola = True
    env.Cosa.append("OTRO")
    env.Cosa.append("MAS")
    env.Cosa = "hello"
    env.Cosa.append("HOLA")

    """
    def __init__(self):
        self._values_ = {}

    def __getattr__(self, name):
        if name.startswith("_") and name.endswith("_"):
            return super(EnvInfo, self).__getattr__(name)

        attr = self._values_.get(name)
        if not attr:
            self._values_[name] = []
        return self._values_[name]

    def __setattr__(self, name, value):
        if name.startswith("_") and name.endswith("_"):
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

    @property
    def dependencies(self):
        return self._dependencies_.items()

    @property
    def deps(self):
        return self._dependencies_.keys()

    def __getitem__(self, item):
        return self._dependencies_[item]

    def update(self, dep_env_info, pkg_name):
        self._dependencies_[pkg_name] = dep_env_info

        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        # With vars if its set the keep the set value
        for varname, value in dep_env_info.vars.items():
            if varname not in self.vars:
                self.vars[varname] = value
            elif isinstance(self.vars[varname], list):
                if isinstance(value, list):
                    self.vars[varname] = merge_lists(self.vars[varname], value)
                else:
                    self.vars[varname] = merge_lists(self.vars[varname], [value])
            else:
                logger.warn("DISCARDED variable %s=%s from %s" % (varname, value, pkg_name))

    def update_deps_env_info(self, dep_env_info):
        assert isinstance(dep_env_info, DepsEnvInfo)
        for pkg_name, env_info in dep_env_info.dependencies:
            self.update(env_info, pkg_name)

    @staticmethod
    def loads(text):
        ret = DepsEnvInfo()
        lib_name = None
        env_info = None
        for line in text.splitlines():
            if not lib_name and not line.startswith("[ENV_"):
                raise ConanException("Error, invalid file format reading env info variables")
            elif line.startswith("[ENV_"):
                if env_info:
                    ret.update(env_info, lib_name)
                lib_name = line[5:-1]
                env_info = EnvInfo()
            else:
                var_name, value = line.split("=", 1)
                if value[0] == "[" and value[-1] == "]":
                    # Take all the items between quotes
                    values = re.findall('"([^"]*)"', value[1:-1])
                    for val in values:
                        getattr(env_info, var_name).append(val)
                else:
                    setattr(env_info, var_name, value)  # peel quotes
        if env_info:
            ret.update(env_info, lib_name)

        return ret

    def dumps(self):
        sections = []
        for name, env_info in self._dependencies_.items():
            sections.append("[ENV_%s]" % name)
            for var, values in sorted(env_info.vars.items()):
                tmp = "%s=" % var
                if isinstance(values, list):
                    tmp += "[%s]" % ",".join(['"%s"' % val for val in values])
                else:
                    tmp += '%s' % values
                sections.append(tmp)
        return "\n".join(sections)
