import os
import re
import traceback
from collections import defaultdict, OrderedDict

from conans.errors import ConanException
from conans.model import Generator
from conans.model.build_info import CppInfo, DepsCppInfo, DepCppInfo
from conans.model.env_info import DepsEnvInfo
from conans.model.user_info import DepsUserInfo
from conans.paths import BUILD_INFO
from conans.util.log import logger


class RootCppTXT(object):
    def __init__(self, cpp_info):
        self.include_paths = "\n".join(p.replace("\\", "/")
                                       for p in cpp_info.include_paths)
        self.lib_paths = "\n".join(p.replace("\\", "/")
                                   for p in cpp_info.lib_paths)
        self.res_paths = "\n".join(p.replace("\\", "/")
                                   for p in cpp_info.res_paths)
        self.build_paths = "\n".join(p.replace("\\", "/")
                                     for p in cpp_info.build_paths)
        self.libs = "\n".join(cpp_info.libs)
        self.system_libs = "\n".join(cpp_info.system_libs)
        self.defines = "\n".join(cpp_info.defines)
        self.cxxflags = "\n".join(cpp_info.cxxflags)
        self.cflags = "\n".join(cpp_info.cflags)
        self.sharedlinkflags = "\n".join(cpp_info.sharedlinkflags)
        self.exelinkflags = "\n".join(cpp_info.exelinkflags)
        self.bin_paths = "\n".join(p.replace("\\", "/")
                                   for p in cpp_info.bin_paths)
        self.sysroot = "%s" % cpp_info.sysroot.replace("\\", "/") if cpp_info.sysroot else ""
        self.frameworks = "\n".join(cpp_info.frameworks)
        self.framework_paths = "\n".join(p.replace("\\", "/")
                                         for p in cpp_info.framework_paths)


class DepCppTXT(RootCppTXT):
    def __init__(self, cpp_info):
        super(DepCppTXT, self).__init__(cpp_info)
        self.version = cpp_info.version
        self.name = cpp_info.get_name(TXTGenerator.name)
        self.rootpath = "%s" % cpp_info.rootpath.replace("\\", "/")
        self.generatornames = "\n".join("%s=%s" % (k, v) for k, v in cpp_info.names.items())
        self.generatorfilenames = "\n".join("%s=%s" % (k, v) for k, v in cpp_info.filenames.items())


class TXTGenerator(Generator):
    name = "txt"
    _USER_INFO_HOST_PREFIX = "USER"
    _USER_INFO_BUILD_PREFIX = "USERBUILD"

    @property
    def filename(self):
        return BUILD_INFO

    @staticmethod
    def loads(text, filter_empty=False):
        user_info_host_idx = text.find("[{}_".format(TXTGenerator._USER_INFO_HOST_PREFIX))
        deps_env_info_idx = text.find("[ENV_")
        user_info_build_idx = text.find("[{}_".format(TXTGenerator._USER_INFO_BUILD_PREFIX))

        user_info_host_txt = deps_env_info_txt = ""

        # Get chunk with deps_cpp_info: from the beginning to the first one of the others
        last_idx = next((x for x in [user_info_host_idx, deps_env_info_idx, user_info_build_idx]
                         if x != -1), None)
        deps_cpp_info_txt = text[:last_idx]

        if user_info_host_idx != -1:
            last_idx = next((x for x in [deps_env_info_idx, user_info_build_idx] if x != -1), None)
            user_info_host_txt = text[user_info_host_idx:last_idx]

        if deps_env_info_idx != -1:
            last_idx = next((x for x in [user_info_build_idx] if x != -1), None)
            deps_env_info_txt = text[deps_env_info_idx:last_idx]

        user_info_build = None
        if user_info_build_idx != -1:
            user_info_build_txt = text[user_info_build_idx:]
            user_info_build = TXTGenerator._loads_user_info(user_info_build_txt,
                                                            TXTGenerator._USER_INFO_BUILD_PREFIX)

        deps_cpp_info = TXTGenerator._loads_cpp_info(deps_cpp_info_txt, filter_empty=filter_empty)
        deps_user_info = TXTGenerator._loads_user_info(user_info_host_txt,
                                                       TXTGenerator._USER_INFO_HOST_PREFIX)
        deps_env_info = DepsEnvInfo.loads(deps_env_info_txt)
        return deps_cpp_info, deps_user_info, deps_env_info, user_info_build

    @staticmethod
    def _loads_user_info(text, user_info_prefix):
        _prefix_for_user_info_host = "[{}_".format(user_info_prefix)
        _prefix_for_user_info_host_length = len(_prefix_for_user_info_host)
        ret = DepsUserInfo()
        lib_name = None
        for line in text.splitlines():
            if not line:
                continue
            if not lib_name and not line.startswith(_prefix_for_user_info_host):
                raise ConanException("Error, invalid file format reading user info variables")
            elif line.startswith(_prefix_for_user_info_host):
                lib_name = line[_prefix_for_user_info_host_length:-1]
            else:
                var_name, value = line.split("=", 1)
                setattr(ret[lib_name], var_name, value)
        return ret

    @staticmethod
    def _loads_cpp_info(text, filter_empty):
        pattern = re.compile(r"^\[([a-zA-Z0-9._:-]+)\]([^\[]+)", re.MULTILINE)

        try:
            # Parse the text
            data = OrderedDict()
            for m in pattern.finditer(text):
                var_name = m.group(1)
                lines = []
                for line in m.group(2).splitlines():
                    line = line.strip()
                    if not line or line[0] == "#":
                        continue
                    lines.append(line)
                if not lines:
                    continue

                tokens = var_name.split(":")
                if len(tokens) == 2:  # has config
                    var_name, config = tokens
                else:
                    config = None
                if 'system_libs' in var_name:
                    tokens = var_name.split("system_libs_", 1)
                    field = 'system_libs'
                else:
                    tokens = var_name.split("_", 1)
                    field = tokens[0]
                dep = tokens[1] if len(tokens) == 2 else None
                if field == "cppflags":
                    field = "cxxflags"
                data.setdefault(dep, defaultdict(dict))
                data[dep][config][field] = lines

            # Build the data structures
            def _relativize_path(p, _rootpath):
                try:
                    return os.path.relpath(p, _rootpath)
                except ValueError:
                    return p

            def _populate_cpp_info(_cpp_info, _data, _rootpath):
                for key, v in _data.items():
                    if key.endswith('dirs'):
                        v = [_relativize_path(it, _rootpath) for it in v]
                        v = ['' if it == '.' else it for it in v]
                    setattr(_cpp_info, key, v)

            if None in data:
                del data[None]

            deps_cpp_info = DepsCppInfo()
            for dep, configs_cpp_info in data.items():
                # Data for the 'cpp_info' object (no configs)
                no_config_data = configs_cpp_info.pop(None)
                rootpath = no_config_data.pop('rootpath')[0]
                dep_cpp_info = CppInfo(dep, rootpath)
                dep_cpp_info.filter_empty = filter_empty
                _ = no_config_data.pop('name')[0]
                version = no_config_data.pop('version', [""])[0]
                dep_cpp_info.version = version
                generatornames = no_config_data.pop("generatornames", [])  # can be empty
                for n in generatornames:
                    gen, value = n.split("=", 1)
                    dep_cpp_info.names[gen] = value
                generatorfilenames = no_config_data.pop("generatorfilenames", [])  # can be empty
                for n in generatorfilenames:
                    gen, value = n.split("=", 1)
                    dep_cpp_info.filenames[gen] = value
                dep_cpp_info.sysroot = no_config_data.pop('sysroot', [""])[0]
                _populate_cpp_info(dep_cpp_info, no_config_data, rootpath)

                # Now the configs
                for config, config_data in configs_cpp_info.items():
                    cpp_info_config = getattr(dep_cpp_info, config)
                    _populate_cpp_info(cpp_info_config, config_data, rootpath)

                # Add to the dependecy list
                deps_cpp_info.add(dep, DepCppInfo(dep_cpp_info))

            return deps_cpp_info

        except Exception as e:
            logger.error(traceback.format_exc())
            raise ConanException("There was an error parsing conanbuildinfo.txt: %s" % str(e))

    @property
    def content(self):
        template = ('[includedirs{dep}{config}]\n{deps.include_paths}\n\n'
                    '[libdirs{dep}{config}]\n{deps.lib_paths}\n\n'
                    '[bindirs{dep}{config}]\n{deps.bin_paths}\n\n'
                    '[resdirs{dep}{config}]\n{deps.res_paths}\n\n'
                    '[builddirs{dep}{config}]\n{deps.build_paths}\n\n'
                    '[libs{dep}{config}]\n{deps.libs}\n\n'
                    '[system_libs{dep}{config}]\n{deps.system_libs}\n\n'
                    '[defines{dep}{config}]\n{deps.defines}\n\n'
                    '[cppflags{dep}{config}]\n{deps.cxxflags}\n\n'  # Backwards compatibility
                    '[cxxflags{dep}{config}]\n{deps.cxxflags}\n\n'
                    '[cflags{dep}{config}]\n{deps.cflags}\n\n'
                    '[sharedlinkflags{dep}{config}]\n{deps.sharedlinkflags}\n\n'
                    '[exelinkflags{dep}{config}]\n{deps.exelinkflags}\n\n'
                    '[sysroot{dep}{config}]\n{deps.sysroot}\n\n'
                    '[frameworks{dep}{config}]\n{deps.frameworks}\n\n'
                    '[frameworkdirs{dep}{config}]\n{deps.framework_paths}\n\n')

        sections = []
        deps = RootCppTXT(self.deps_build_info)
        all_flags = template.format(dep="", deps=deps, config="")
        sections.append(all_flags)

        for config, cpp_info in self.deps_build_info.configs.items():
            deps = DepCppTXT(cpp_info)
            all_flags = template.format(dep="", deps=deps, config=":" + config)
            sections.append(all_flags)

        # Makes no sense to have an accumulated rootpath
        template_deps = (template + '[rootpath{dep}]\n{deps.rootpath}\n\n' +
                         '[name{dep}]\n{deps.name}\n\n' +
                         '[version{dep}]\n{deps.version}\n\n' +
                         '[generatornames{dep}]\n{deps.generatornames}\n\n' +
                         '[generatorfilenames{dep}]\n{deps.generatorfilenames}\n\n')

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            dep = "_" + dep_name
            deps = DepCppTXT(dep_cpp_info)
            dep_flags = template_deps.format(dep=dep, deps=deps, config="")
            sections.append(dep_flags)

            for config, cpp_info in dep_cpp_info.configs.items():
                deps = DepCppTXT(cpp_info)
                all_flags = template.format(dep=dep, deps=deps, config=":" + config)
                sections.append(all_flags)

        def append_user_info(prefix, user_info_data):
            for dep, the_vars in sorted(user_info_data.items()):
                sections.append("[{prefix}_{dep_name}]".format(prefix=prefix, dep_name=dep))
                for name, value in sorted(the_vars.vars.items()):
                    sections.append("%s=%s" % (name, value))

        # Generate the user_info variables for HOST as [USER_{DEP_NAME}] and values with key=value
        append_user_info(self._USER_INFO_HOST_PREFIX, self._deps_user_info)

        # Generate the env info variables as [ENV_{DEP_NAME}] and then the values with key=value
        sections.append(self._deps_env_info.dumps())

        # Generate the user_info variables for BUILD as [USERBUILD_{DEP_NAME}]
        if self._user_info_build:
            append_user_info(self._USER_INFO_BUILD_PREFIX, self._user_info_build)

        return "\n".join(sections)
