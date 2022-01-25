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


def get_apple_sdk_name(conanfile):
    """
    Returns the 'os.sdk' (SDK name) field value. Every user should specify it because
    there could be several ones depending on the OS architecture.

    Note: In case of MacOS it'll be the same for all the architectures.
    """
    os_ = conanfile.settings.get_safe('os')
    os_sdk = conanfile.settings.get_safe('os.sdk')
    if os_sdk:
        return os_sdk
    elif os_ == "Macos":  # it has only a single value for all the architectures
        return "macosx"
    elif is_apple_os(os_):
        raise ConanException("Please, specify a suitable value for os.sdk.")


def apple_min_version_flag(os_version, os_sdk, subsystem):
    """compiler flag name which controls deployment target"""
    if not os_version or not os_sdk:
        return ''

    # FIXME: This guess seems wrong, nothing has to be guessed, but explicit
    flag = {'macosx': '-mmacosx-version-min',
            'iphoneos': '-mios-version-min',
            'iphonesimulator': '-mios-simulator-version-min',
            'watchos': '-mwatchos-version-min',
            'watchsimulator': '-mwatchos-simulator-version-min',
            'appletvos': '-mtvos-version-min',
            'appletvsimulator': '-mtvos-simulator-version-min'}.get(str(os_sdk))
    if subsystem == 'catalyst':
        # especial case, despite Catalyst is macOS, it requires an iOS version argument
        flag = '-mios-version-min'
    if not flag:
        return ''
    return "%s=%s" % (flag, os_version)


def apple_sdk_path(conanfile):
    sdk_path = conanfile.conf["tools.apple:sdk_path"]
    if not sdk_path:
        sdk_path = XCRun(conanfile.settings).sdk_path
    return sdk_path


class XCRun(object):

    def __init__(self, settings, sdk=None):
        """sdk=False will skip the flag
           sdk=None will try to adjust it automatically"""
        if sdk is None and settings:
            sdk = settings.get_safe('os.sdk')
        self.sdk = sdk

    def _invoke(self, args):
        def cmd_output(cmd):
            from conans.util.runners import check_output_runner
            return check_output_runner(cmd).strip()

        command = ['xcrun']
        if self.sdk:
            command.extend(['-sdk', self.sdk])
        command.extend(args)
        return cmd_output(command)

    def find(self, tool):
        """find SDK tools (e.g. clang, ar, ranlib, lipo, codesign, etc.)"""
        return self._invoke(['--find', tool])

    @property
    def sdk_path(self):
        """obtain sdk path (aka apple sysroot or -isysroot"""
        return self._invoke(['--show-sdk-path'])

    @property
    def sdk_version(self):
        """obtain sdk version"""
        return self._invoke(['--show-sdk-version'])

    @property
    def sdk_platform_path(self):
        """obtain sdk platform path"""
        return self._invoke(['--show-sdk-platform-path'])

    @property
    def sdk_platform_version(self):
        """obtain sdk platform version"""
        return self._invoke(['--show-sdk-platform-version'])

    @property
    def cc(self):
        """path to C compiler (CC)"""
        return self.find('clang')

    @property
    def cxx(self):
        """path to C++ compiler (CXX)"""
        return self.find('clang++')

    @property
    def ar(self):
        """path to archiver (AR)"""
        return self.find('ar')

    @property
    def ranlib(self):
        """path to archive indexer (RANLIB)"""
        return self.find('ranlib')

    @property
    def strip(self):
        """path to symbol removal utility (STRIP)"""
        return self.find('strip')

    @property
    def libtool(self):
        """path to libtool"""
        return self.find('libtool')
