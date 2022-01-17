from conan.tools.build.cpu import build_jobs
from conan.tools.build.cross_building import cross_building


def use_win_mingw(conanfile):
    os_build = conanfile.settings_build.get_safe('os')
    if os_build == "Windows":
        compiler = conanfile.settings.get_safe("compiler")
        sub = conanfile.settings.get_safe("os.subsystem")
        if sub in ("cygwin", "msys2", "msys") or compiler == "qcc":
            return False
        else:
            return True
    return False
