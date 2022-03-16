def preprocess(settings):
    _fill_runtime(settings)
    # Check cppstd doesn't need to be harcoded in Conan, instead it should
    # probably be hook-like code, user side (and opt-in/opt-out)


def _fill_runtime(settings):
    try:
        if settings.compiler == "Visual Studio":
            if settings.get_safe("compiler.runtime") is None:
                runtime = "MDd" if settings.get_safe("build_type") == "Debug" else "MD"
                settings.compiler.runtime = runtime
        elif settings.compiler == "msvc":
            if settings.get_safe("compiler.runtime_type") is None:
                runtime = "Debug" if settings.get_safe("build_type") == "Debug" else "Release"
                settings.compiler.runtime_type = runtime
    except Exception:  # If the settings structure doesn't match these general
        # asumptions, like unexistant runtime
        pass
