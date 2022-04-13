import os

from conans.cli.output import ConanOutput

CONAN_TOOLCHAIN_ARGS_FILE = "conanbuild.conf"
CONAN_TOOLCHAIN_ARGS_SECTION = "toolchain"


def get_lib_file_path(libdirs, lib_name):
    output = ConanOutput()
    for libdir in libdirs:
        if not os.path.exists(libdir):
            output.warning("The library folder doesn't exist: {}".format(libdir))
            continue
        files = os.listdir(libdir)
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in (".so", ".lib", ".a", ".dylib", ".bc"):
                if ext != ".lib" and name.startswith("lib"):
                    name = name[3:]
            else:
                continue
            if lib_name == name:
                return os.path.join(libdir, f)
    output.warning("The library {} cannot be found in the dependency".format(lib_name))


def get_dll_file_path(bindirs, implib_name):
    output = ConanOutput()
    for bindir in bindirs:
        if not os.path.exists(bindir):
            output.warning("The library folder doesn't exist: {}".format(bindir))
            continue
        files = os.listdir(bindir)
        for f in files:
            name, ext = os.path.splitext(f)
            if ext.lower() == ".dll" and name.lower().startswith(implib_name.lower()):
                return os.path.join(bindir, f)
