import json

from conans.model import Generator


def serialize_cpp_info(cpp_info):
    keys = [
        "version",
        "description",
        "rootpath",
        "sysroot",
        "include_paths", "lib_paths", "bin_paths", "build_paths", "res_paths",
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
        info["dependencies"] = []
        for depname, cpp_info in self.deps_build_info.dependencies:
            serialized_info = serialize_cpp_info(cpp_info)
            serialized_info["name"] = depname
            info["dependencies"].append(serialized_info)

        return json.dumps(info, indent=2)
