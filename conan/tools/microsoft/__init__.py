# noinspection PyUnresolvedReferences
from .toolchain import MSBuildToolchain
from .msbuild import MSBuild
from .msbuilddeps import MSBuildDeps


def msvc_runtime_flag(conanfile):
    settings = conanfile.settings
    compiler = settings.get_safe("compiler")
    runtime = settings.get_safe("compiler.runtime")
    if compiler == "Visual Studio":
        return runtime
    if compiler == "msvc":
        runtime_type = settings.get_safe("compiler.runtime_type")
        if runtime == "static":
            return "MTd" if runtime_type == "Debug" else "MT"
        else:
            return "MDd" if runtime_type == "Debug" else "MD"
