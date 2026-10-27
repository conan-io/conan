from conan.api.output import ConanOutput
from conan.internal.api.detect.detect_api import detect_os, detect_arch, default_msvc_runtime, \
    detect_libcxx, detect_cppstd, detect_default_compiler, default_compiler_version, detect_libc
from conan.internal.default_settings import default_settings_yml
from conan.internal.model.settings import Settings


def detect_defaults_settings():
    """ try to deduce current machine values without any constraints at all
    :return: A list with default settings
    """
    result = []
    the_os = detect_os()
    result.append(("os", the_os))

    arch = detect_arch()
    if arch:
        result.append(("arch", arch))
    if the_os == "Linux":
        result.extend(_detect_libc_settings())
    compiler, version, compiler_exe = detect_default_compiler()
    if not compiler:
        result.append(("build_type", "Release"))
        ConanOutput().warning("No compiler was detected (one may not be needed)")
        return result

    result.append(("compiler", compiler))
    result.append(("compiler.version", default_compiler_version(compiler, version)))

    runtime, runtime_version = default_msvc_runtime(compiler)
    if runtime:
        result.append(("compiler.runtime", runtime))
    if runtime_version:
        result.append(("compiler.runtime_version", runtime_version))
    libcxx = detect_libcxx(compiler, version, compiler_exe)
    if libcxx:
        result.append(("compiler.libcxx", libcxx))
    cppstd = detect_cppstd(compiler, version)
    if cppstd:
        result.append(("compiler.cppstd", cppstd))
    result.append(("build_type", "Release"))
    return result


def _detect_libc_settings():
    """ The detected libc version is only defined if it is a known version in the default
    settings.yml, as rounding it to a known one would produce a wrong binary compatibility
    """
    libc, libc_version = detect_libc()
    if libc is None:
        return []
    libc = {"gnu": "glibc"}.get(libc, libc)
    libc_definitions = Settings.loads(default_settings_yml).os.possible_values()["Linux"]["libc"]
    if libc not in libc_definitions:
        ConanOutput().warning(f"Detected libc '{libc}' is not defined in settings.yml")
        return []
    result = [("os.libc", libc)]
    if libc_version in libc_definitions[libc]["version"]:
        result.append(("os.libc.version", libc_version))
    else:
        ConanOutput().warning(f"Detected {libc} version '{libc_version}' is not defined in "
                              f"settings.yml, 'os.libc.version' will not be defined in the profile")
    return result
