import os

from conans.errors import ConanException
from conans.util.runners import check_output_runner


def is_apple_os(os_):
    """returns True if OS is Apple one (Macos, iOS, watchOS or tvOS"""
    return str(os_) in ['Macos', 'iOS', 'watchOS', 'tvOS']


def to_apple_arch(arch, default=None):
    """converts conan-style architecture into Apple-style arch"""
    return {'x86': 'i386',
            'x86_64': 'x86_64',
            'armv7': 'armv7',
            'armv8': 'arm64',
            'armv8_32': 'arm64_32',
            'armv8.3': 'arm64e',
            'armv7s': 'armv7s',
            'armv7k': 'armv7k'}.get(arch, default)


def get_apple_sdk_fullname(conanfile):
    """
    Returns the 'os.sdk' + 'os.sdk_version ' value. Every user should specify it because
    there could be several ones depending on the OS architecture.

    Note: In case of MacOS it'll be the same for all the architectures.
    """
    os_ = conanfile.settings.get_safe('os')
    os_sdk = conanfile.settings.get_safe('os.sdk')
    os_sdk_version = conanfile.settings.get_safe('os.sdk_version') or ""

    if os_sdk:
        return "{}{}".format(os_sdk, os_sdk_version)
    elif os_ == "Macos":  # it has only a single value for all the architectures
        return "{}{}".format("macosx", os_sdk_version)
    elif is_apple_os(os_):
        raise ConanException("Please, specify a suitable value for os.sdk.")


def apple_min_version_flag(os_version, os_sdk, subsystem):
    """compiler flag name which controls deployment target"""
    if not os_version or not os_sdk:
        return ''

    # FIXME: This guess seems wrong, nothing has to be guessed, but explicit
    flag = ''
    if 'macosx' in os_sdk:
        flag = '-mmacosx-version-min'
    elif 'iphoneos' in os_sdk:
        flag = '-mios-version-min'
    elif 'iphonesimulator' in os_sdk:
        flag = '-mios-simulator-version-min'
    elif 'watchos' in os_sdk:
        flag = '-mwatchos-version-min'
    elif 'watchsimulator' in os_sdk:
        flag = '-mwatchos-simulator-version-min'
    elif 'appletvos' in os_sdk:
        flag = '-mtvos-version-min'
    elif 'appletvsimulator' in os_sdk:
        flag = '-mtvos-simulator-version-min'

    if subsystem == 'catalyst':
        # especial case, despite Catalyst is macOS, it requires an iOS version argument
        flag = '-mios-version-min'

    return f"{flag}={os_version}" if flag else ''


def fix_apple_shared_install_name(conanfile):
    """
    Search for all the *dylib* files in the conanfile's *package_folder* and fix
    both the ``LC_ID_DYLIB`` and ``LC_LOAD_DYLIB`` fields on those files using the
    *install_name_tool* utility available in macOS to set ``@rpath``.
    """

    def _get_install_name(path_to_dylib):
        command = "otool -D {}".format(path_to_dylib)
        installname = check_output_runner(command).strip().split(":")[1].strip()
        return installname

    def _osx_collect_dylibs(lib_folder):
        return [os.path.join(full_folder, f) for f in os.listdir(lib_folder) if f.endswith(".dylib")
                and not os.path.islink(os.path.join(lib_folder, f))]

    def _fix_install_name(dylib_path, new_name):
        command = f"install_name_tool {dylib_path} -id {new_name}"
        conanfile.run(command)

    def _fix_dep_name(dylib_path, old_name, new_name):
        command = f"install_name_tool {dylib_path} -change {old_name} {new_name}"
        conanfile.run(command)

    substitutions = {}

    if is_apple_os(conanfile.settings.get_safe("os")) and conanfile.options.get_safe("shared", False):
        libdirs = getattr(conanfile.cpp.package, "libdirs")
        for libdir in libdirs:
            full_folder = os.path.join(conanfile.package_folder, libdir)
            shared_libs = _osx_collect_dylibs(full_folder)
            # fix LC_ID_DYLIB in first pass
            for shared_lib in shared_libs:
                install_name = _get_install_name(shared_lib)
                rpath_name = f"@rpath/{os.path.basename(install_name)}"
                _fix_install_name(shared_lib, rpath_name)
                substitutions[install_name] = rpath_name

            # fix dependencies in second pass
            for shared_lib in shared_libs:
                for old, new in substitutions.items():
                    _fix_dep_name(shared_lib, old, new)
