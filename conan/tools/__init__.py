import os

CONAN_TOOLCHAIN_ARGS_FILE = "conanbuild.conf"
CONAN_TOOLCHAIN_ARGS_SECTION = "toolchain"


def get_lib_file_path(libdirs, lib, conanfile):
    for libdir in libdirs:
        if not os.path.exists(libdir):
            conanfile.output.warning("The library folder doesn't exist: {}".format(libdir))
            continue
        files = os.listdir(libdir)
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in (".so", ".lib", ".a", ".dylib", ".bc"):
                if ext != ".lib" and name.startswith("lib"):
                    name = name[3:]
            if lib == name:
                return os.path.join(libdir, f)
    conanfile.output.warning("The library {} cannot be found in the dependency".format(lib))
