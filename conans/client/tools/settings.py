from conans.client.build.cppstd_flags import cppstd_from_settings, cppstd_default
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.version import Version


def deduced_cppstd(conanfile):
    """ Return either the current cppstd or the default one used by the current compiler

        1. If settings.compiler.cppstd is not None - will return settings.compiler.cppstd
        2. It settings.compiler.cppstd is None - will use compiler to deduce (reading the
            default from cppstd_default)
        3. If settings.compiler is None - will raise a ConanInvalidConfiguration exception
        4. If can't detect the default cppstd for settings.compiler - will return None

    :param conanfile: ConanFile instance with compiler and cppstd information
    """
    cppstd = cppstd_from_settings(conanfile.settings)
    if cppstd:
        return cppstd

    compiler = conanfile.settings.get_safe("compiler")
    if not compiler:
        raise ConanInvalidConfiguration("Could not obtain cppstd because either compiler is not "
                                        "specified in the profile or the 'settings' field of the "
                                        "recipe is missing")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    if not compiler_version:
        raise ConanInvalidConfiguration("Could not obtain cppstd because compiler.version "
                                        "is not specified in the profile")

    return cppstd_default(compiler, compiler_version)


def normalized_cppstd(cppstd):
    """ Return a normalized cppstd value by removing extensions and
        adding a millennium to allow ordering on it

    :param cppstd: cppstd version
    """
    if not isinstance(cppstd, str) and not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must either be a string or a digit")

    def remove_extension(_cppstd):
        return str(_cppstd).replace("gnu", "")

    def add_millennium(_cppstd):
        return "19%s" % _cppstd if _cppstd == "98" else "20%s" % _cppstd

    return add_millennium(remove_extension(cppstd))


def check_gnu_extension(cppstd):
    """ Check if cppstd enables gnu extensions

    :param cppstd: cppstd version
    """
    if not isinstance(cppstd, str) and not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must either be a string or a digit")

    if not str(cppstd).startswith("gnu"):
        raise ConanInvalidConfiguration("The cppstd GNU extension is required")


def check_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if the current cppstd fits the minimal version required.

        In case the current cppstd doesn't fit the minimal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    current_cppstd = deduced_cppstd(conanfile)
    if not current_cppstd:
        raise ConanInvalidConfiguration("Could not detect default cppstd for the current compiler.")

    if gnu_extensions:
        check_gnu_extension(current_cppstd)

    if normalized_cppstd(current_cppstd) < normalized_cppstd(cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than the required C++ "
                                        "standard ({}).".format(current_cppstd, cppstd))


def valid_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the minimal version required.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    try:
        check_min_cppstd(conanfile, cppstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True


def check_max_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if the current cppstd fits the maximal version required.

        In case the current cppstd doesn't fit the maximal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    current_cppstd = deduced_cppstd(conanfile)
    if not current_cppstd:
        raise ConanInvalidConfiguration("Could not detect default cppstd for the current compiler.")

    if gnu_extensions:
        check_gnu_extension(current_cppstd)

    if normalized_cppstd(current_cppstd) > normalized_cppstd(cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is higher than the required C++ "
                                        "standard ({}).".format(current_cppstd, cppstd))


def valid_max_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the maximal version required.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    try:
        check_max_cppstd(conanfile, cppstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True


def check_cppstd(conanfile, minimum=None, maximum=None, excludes=[], gnu_extensions=False, strict=False):
    """ Check if the current cppstd fits specified requirements

        In case the current cppstd doesn't fit specified requirements
        a ConanInvalidConfiguration exception will be raised.

        In case information about cppstd is lacking
        a ConanUnknownConfiguration exception will be raised.

    :param conanfile: ConanFile instance
    :param minimum: Minimal cppstd version required
    :param maximum: Maximal cppstd version required
    :param excludes: A list of cppstd version excluded
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    :param strict: Unkown configurations are invalid
    """
    if minimum and not str(minimum).isdigit():
        raise ConanException("minimum parameter must be a number")
    if maximum and not str(maximum).isdigit():
        raise ConanException("maximum parameter must be a number")
    if not isinstance(excludes, list):
        raise ConanException("excludes parameter must be a list")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")
    if not isinstance(strict, bool):
        raise ConanException("strict parameter must be a bool")
    if minimum and maximum:
        if normalized_cppstd(minimum) > normalized_cppstd(maximum):
            raise ConanException("minimum parameter is bigger than the maximum parameter")

    current_cppstd = deduced_cppstd(conanfile)
    if not current_cppstd:
        msg = "Default standard version information is missing for the current compiler"
        if strict:
            raise ConanInvalidConfiguration(msg)
        conanfile.output.warn(msg)
        return

    if gnu_extensions:
        check_gnu_extension(current_cppstd)

    if minimum:
        if normalized_cppstd(current_cppstd) < normalized_cppstd(minimum):
            raise ConanInvalidConfiguration("Current cppstd ({}) is less than the minimum required C++ "
                                            "standard ({})".format(current_cppstd, minimum))

    if maximum:
        if normalized_cppstd(current_cppstd) > normalized_cppstd(maximum):
            raise ConanInvalidConfiguration("Current cppstd ({}) is higher than the maximum required C++ "
                                            "standard ({})".format(current_cppstd, maximum))

    if current_cppstd in excludes:
        raise ConanInvalidConfiguration(
            "Current cppstd ({}) is excluded from requirements".format(current_cppstd))


def check_compiler(conanfile, required, strict=False):
    """ Check if the current compiler fits specified requirements

        In case the current compiler doesn't fit specified requirements
        a ConanInvalidConfiguration exception will be raised.

        In case information about compiler is lacking and strict flag is set
        a ConanUnknownConfiguration exception will be raised.

    :param conanfile: ConanFile instance
    :param required: A dict of required compiler versions required
    :param strict: Unkown configurations are invalid
    """
    if not isinstance(required, dict):
        raise ConanException("required parameter must be a dict")
    if not isinstance(strict, bool):
        raise ConanException("strict parameter must be a bool")

    compiler = conanfile.settings.get_safe("compiler")
    if not compiler:
        raise ConanInvalidConfiguration("Could not obtain cppstd because either compiler is not "
                                        "specified in the profile or the 'settings' field of the "
                                        "recipe is missing")
    try:
        if compiler not in required:
            raise ConanInvalidConfiguration("Compiler support information is missing")
    except ConanInvalidConfiguration as e:
        if strict:
            raise
        conanfile.output.warn(e)
        return

    compiler_version = conanfile.settings.get_safe("compiler.version")
    if not compiler_version:
        raise ConanInvalidConfiguration("Could not obtain cppstd because compiler.version "
                                        "is not specified in the profile")
    version = Version(compiler_version)
    if version < required[compiler]:
        raise ConanInvalidConfiguration(
            "At least {} {} is required".format(compiler, required[compiler]))
