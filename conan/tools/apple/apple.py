from conans.errors import ConanException


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
