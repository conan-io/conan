import json

from conans.model import Generator


def serialize_cpp_info(cpp_info):
    keys = [
        "version",
        "description",
        "rootpath",
        "sysroot",
        "includedirs", "libdirs", "bindirs", "builddirs", "resdirs",
        "libs",
        "defines", "cflags", "cppflags", "sharedlinkflags", "exelinkflags",
    ]
    res = {}
    for key in keys:
        res[key] = getattr(cpp_info, key)
    return res


class JsonGenerator(Generator):
    @property
    def filename(self):
        return "conaninfo.json"

    @property
    def content(self):
        info = {}
        info["deps_env_info"] = self.deps_env_info.vars
        info["deps_user_info"] = self.get_deps_user_info()
        info["dependencies"] = self.get_dependencies_info()
        return json.dumps(info, indent=2)

    def get_deps_user_info(self):
        res = {}
        for key, value in self.deps_user_info.items():
            res[key] = value.vars
        return res

    def get_dependencies_info(self):
        res = []
        for depname, cpp_info in self.deps_build_info.dependencies:
            serialized_info = serialize_cpp_info(cpp_info)
            serialized_info["name"] = depname
            res.append(serialized_info)
        return res
