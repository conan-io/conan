from conans.errors import ConanException


def preprocess(settings):
    if settings.get_safe("compiler") == "msvc" and settings.get_safe("compiler.runtime"):
        if settings.get_safe("compiler.runtime_type") is None:
            runtime = "Debug" if settings.get_safe("build_type") == "Debug" else "Release"
            try:
                settings.compiler.runtime_type = runtime
            except ConanException:
                pass
