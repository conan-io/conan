import re
import traceback

from conans.errors import ConanException
from conans.model import Generator
from conans.model.build_info import DepsCppInfo, CppInfo
from conans.model.env_info import DepsEnvInfo
from conans.model.user_info import DepsUserInfo
from conans.paths import BUILD_INFO
from conans.util.log import logger


class DepsCppTXT(object):
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
        self.defines = "\n".join(cpp_info.defines)
        self.cppflags = "\n".join(cpp_info.cppflags)
        self.cflags = "\n".join(cpp_info.cflags)
        self.sharedlinkflags = "\n".join(cpp_info.sharedlinkflags)
        self.exelinkflags = "\n".join(cpp_info.exelinkflags)
        self.bin_paths = "\n".join(p.replace("\\", "/")
                                   for p in cpp_info.bin_paths)
        self.rootpath = "%s" % cpp_info.rootpath.replace("\\", "/")
        self.sysroot = "%s" % cpp_info.sysroot.replace("\\", "/") if cpp_info.sysroot else ""


class TXTGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO

    @staticmethod
    def loads(text):
        user_defines_index = text.find("[USER_")
        env_defines_index = text.find("[ENV_")
        if user_defines_index != -1:
            deps_cpp_info_txt = text[:user_defines_index]
            if env_defines_index != -1:
                user_info_txt = text[user_defines_index:env_defines_index]
                deps_env_info_txt = text[env_defines_index:]
            else:
                user_info_txt = text[user_defines_index:]
                deps_env_info_txt = ""
        else:
            if env_defines_index != -1:
                deps_cpp_info_txt = text[:env_defines_index]
                deps_env_info_txt = text[env_defines_index:]
            else:
                deps_cpp_info_txt = text
                deps_env_info_txt = ""

            user_info_txt = ""

        deps_cpp_info = TXTGenerator._loads_cpp_info(deps_cpp_info_txt)
        deps_user_info = TXTGenerator._loads_deps_user_info(user_info_txt)
        deps_env_info = DepsEnvInfo.loads(deps_env_info_txt)
        return deps_cpp_info, deps_user_info, deps_env_info

    @staticmethod
    def _loads_deps_user_info(text):
        ret = DepsUserInfo()
        lib_name = None
        for line in text.splitlines():
            if not line:
                continue
            if not lib_name and not line.startswith("[USER_"):
                raise ConanException("Error, invalid file format reading user info variables")
            elif line.startswith("[USER_"):
                lib_name = line[6:-1]
            else:
                var_name, value = line.split("=", 1)
                setattr(ret[lib_name], var_name, value)
        return ret

    @staticmethod
    def _loads_cpp_info(text):
        pattern = re.compile(r"^\[([a-zA-Z0-9._:-]+)\]([^\[]+)", re.MULTILINE)
        result = DepsCppInfo()

        try:
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
                tokens = var_name.split("_", 1)
                field = tokens[0]
                if len(tokens) == 2:
                    dep = tokens[1]
                    dep_cpp_info = result._dependencies.setdefault(dep, CppInfo(root_folder=""))
                    if field in ["rootpath", "sysroot"]:
                        lines = lines[0]
                    item_to_apply = dep_cpp_info
                else:
                    if field == "sysroot":
                        lines = lines[0]
                    item_to_apply = result
                if config:
                    config_deps = getattr(item_to_apply, config)
                    setattr(config_deps, field, lines)
                else:
                    setattr(item_to_apply, field, lines)
        except Exception as e:
            logger.error(traceback.format_exc())
            raise ConanException("There was an error parsing conanbuildinfo.txt: %s" % str(e))

        return result

    @property
    def content(self):
        template = ('[includedirs{dep}{config}]\n{deps.include_paths}\n\n'
                    '[libdirs{dep}{config}]\n{deps.lib_paths}\n\n'
                    '[bindirs{dep}{config}]\n{deps.bin_paths}\n\n'
                    '[resdirs{dep}{config}]\n{deps.res_paths}\n\n'
                    '[builddirs{dep}{config}]\n{deps.build_paths}\n\n'
                    '[libs{dep}{config}]\n{deps.libs}\n\n'
                    '[defines{dep}{config}]\n{deps.defines}\n\n'
                    '[cppflags{dep}{config}]\n{deps.cppflags}\n\n'
                    '[cflags{dep}{config}]\n{deps.cflags}\n\n'
                    '[sharedlinkflags{dep}{config}]\n{deps.sharedlinkflags}\n\n'
                    '[exelinkflags{dep}{config}]\n{deps.exelinkflags}\n\n'
                    '[sysroot{dep}{config}]\n{deps.sysroot}\n\n')

        sections = []
        deps = DepsCppTXT(self.deps_build_info)
        all_flags = template.format(dep="", deps=deps, config="")
        sections.append(all_flags)

        for config, cpp_info in self.deps_build_info.configs.items():
            deps = DepsCppTXT(cpp_info)
            all_flags = template.format(dep="", deps=deps, config=":" + config)
            sections.append(all_flags)

        # Makes no sense to have an accumulated rootpath
        template_deps = template + '[rootpath{dep}]\n{deps.rootpath}\n\n'

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            dep = "_" + dep_name
            deps = DepsCppTXT(dep_cpp_info)
            dep_flags = template_deps.format(dep=dep, deps=deps, config="")
            sections.append(dep_flags)

            for config, cpp_info in dep_cpp_info.configs.items():
                deps = DepsCppTXT(cpp_info)
                all_flags = template.format(dep=dep, deps=deps, config=":" + config)
                sections.append(all_flags)

        # Generate the user info variables as [USER_{DEP_NAME}] and then the values with key=value
        for dep, the_vars in self._deps_user_info.items():
            sections.append("[USER_%s]" % dep)
            for name, value in sorted(the_vars.vars.items()):
                sections.append("%s=%s" % (name, value))

        # Generate the env info variables as [ENV_{DEP_NAME}] and then the values with key=value
        sections.append(self._deps_env_info.dumps())

        return "\n".join(sections)
