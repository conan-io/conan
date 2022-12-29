import json

from conans.model import Generator


def serialize_user_info(user_info):
    res = {}
    for key, value in user_info.items():
        res[key] = value.vars
    return res


class JsonGenerator(Generator):
    @property
    def filename(self):
        return "conanbuildinfo.json"

    @property
    def content(self):
        info = {}
        info["deps_env_info"] = self.deps_env_info.vars
        info["deps_user_info"] = serialize_user_info(self.deps_user_info)
        info["dependencies"] = self.get_dependencies_info()
        info["settings"] = self.get_settings()
        info["options"] = self.get_options()
        if self._user_info_build:
            info["user_info_build"] = serialize_user_info(self._user_info_build)

        return json.dumps(info, indent=2)

    def get_dependencies_info(self):
        res = []
        for depname, cpp_info in self.deps_build_info.dependencies:
            serialized_info = self.serialize_cpp_info(depname, cpp_info)
            for cfg, cfg_cpp_info in cpp_info.configs.items():
                serialized_info.setdefault("configs", {})[cfg] = self.serialize_cpp_info(depname,
                                                                                         cfg_cpp_info)
            res.append(serialized_info)
        return res

    def get_settings(self):
        settings = {}
        for key, value in self.settings.items():
            settings[key] = value
        return settings

    def get_options(self):
        options = {}
        for req in self.conanfile.requires:
            options[req] = {}
            for key, value in self.conanfile.options[req].items():
                options[req][key] = value
        return options

    def serialize_cpp_info(self, depname, cpp_info):
        keys = [
            "version",
            "description",
            "rootpath",
            "sysroot",
            "include_paths", "lib_paths", "bin_paths", "build_paths", "res_paths",
            "libs",
            "system_libs",
            "defines", "cflags", "cxxflags", "sharedlinkflags", "exelinkflags",
            "frameworks", "framework_paths", "names", "filenames",
            "build_modules", "build_modules_paths"
        ]
        res = {}
        for key in keys:
            res[key] = getattr(cpp_info, key)
        res["cppflags"] = cpp_info.cxxflags  # Backwards compatibility
        res["name"] = depname

        # FIXME: trick for NewCppInfo objects when declared layout
        try:
            if cpp_info.version is None:
                res["version"] = self.conanfile.dependencies.get(depname).ref.version
        except Exception:
            pass

        return res
