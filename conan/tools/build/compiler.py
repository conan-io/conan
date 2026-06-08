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

def compiler_executables(conanfile):
    """
    Returns the C and C++ compiler executables based on compiler settings.

    :return: dict with "c" and "cpp" keys, or None if not applicable
    """
    compiler = conanfile.settings.get_safe("compiler")
    if compiler == "intel-cc":
        mode = conanfile.settings.get_safe("compiler.mode")
        version = conanfile.settings.get_safe("compiler.version")
        if mode == "classic":
            return {"c": "icc", "cpp": "icpc"}
        elif mode == "dpcpp" and int(version.split(".")[0]) < 2024:
            return {"c": "icx", "cpp": "dpcpp"}  # dpcpp deprecated since 2024.0
        else:  # icx or dpcpp >= 2024
            return {"c": "icx", "cpp": "icpx"}
    return None
