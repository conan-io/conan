from conan.errors import ConanInvalidConfiguration, ConanException
from conan.internal.model.version import Version


def check_min_compiler_version(conanfile, compiler_restrictions):
    """(Experimental) Checks if the current compiler and its version meet the minimum requirements.

    :param conanfile: The current recipe object. Always use ``self``.
    :param compiler_restrictions:
        A list of tuples, where each tuple contains:

        - **compiler** (*str*): The name of the compiler (e.g., "gcc", "msvc").
        - **min_version** (*str*): The minimum required version as a string (e.g., "14", "19.0").
        - **reason** (*str*): A string explaining the reason for the version requirement.
    :raises ConanException:
        If the 'compiler' or 'compiler.version' settings are not defined.
    :raises ConanInvalidConfiguration:
        If the found compiler version is less than the specified minimum version for that compiler.

    :Example:
        .. code-block:: python

            def validate(self):
                compiler_restrictions = [
                    ("clang", "14", "requires C++20 coroutines support"),
                    ("gcc", "12", "requires C++20 modules support")
                ]
                check_min_compiler_version(self, compiler_restrictions)
    """
    compiler_value = conanfile.settings.get_safe("compiler")
    if not compiler_value:
        raise ConanException("Called check_min_compiler_version with no compiler defined")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    if not compiler_version:
        raise ConanException("Called check_min_compiler_version with no compiler.version defined")

    for compiler, min_version, reason in compiler_restrictions:
        if compiler_value == compiler:
            if Version(compiler_version) < Version(min_version):
                ref = conanfile.ref if hasattr(conanfile, "ref") else conanfile.name
                raise ConanInvalidConfiguration(
                    f"{ref} requires {compiler} >= {min_version}, but {compiler} {compiler_version} was found\n"
                    f"Reason: {reason}")
            break


def get_compiler_executables(conanfile):
    """
    Returns compiler executables dict with priority:
    1. tools.build:compiler_executables conf
    2. CC/CXX from buildenv
    3. Known defaults based on compiler setting (intel-cc, emcc)

    :param conanfile: The current recipe object.
    :return: dict with "c", "cpp" and other compiler keys if defined.
    """
    result = {}

    # 1. Read from conf
    compilers_by_conf = conanfile.conf.get("tools.build:compiler_executables",
                                           default={}, check_type=dict)
    result.update(compilers_by_conf)

    # 2. Fill from buildenv if not in conf
    if "c" not in result or "cpp" not in result:
        buildenv = conanfile.buildenv_build.vars(conanfile)
        if "c" not in result and buildenv.get("CC"):
            result["c"] = buildenv.get("CC")
        if "cpp" not in result and buildenv.get("CXX"):
            result["cpp"] = buildenv.get("CXX")

    # 3. Fill known defaults if c and cpp still missing
    if "c" not in result and "cpp" not in result:
        compiler = conanfile.settings.get_safe("compiler")
        if compiler == "intel-cc":
            mode = conanfile.settings.get_safe("compiler.mode")
            if mode == "classic":
                return {"c": "icc", "cpp": "icpc"}
            elif mode == "dpcpp":
                return {"c": "icx", "cpp": "dpcpp"}
            elif mode == "icx":
                return {"c": "icx", "cpp": "icpx"}
        if compiler == "emcc":
            return {"c": "emcc", "cpp": "em++"}

    return result
