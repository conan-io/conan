def preprocess(settings):
    if settings.get_safe("compiler") == "msvc":
        if settings.get_safe("compiler.runtime_type") is None:
            runtime = "Debug" if settings.get_safe("build_type") == "Debug" else "Release"
            settings.compiler.runtime_type = runtime

