from conan.tools.apple import to_apple_arch
from conans.errors import ConanException


class XcodeBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._build_type = conanfile.settings.get_safe("build_type")
        self._arch = to_apple_arch(self._conanfile)
        self._sdk = conanfile.settings.get_safe("os.sdk") or ""
        self._sdk_version = conanfile.settings.get_safe("os.sdk_version") or ""

    @property
    def _verbosity(self):
        verbosity = self._conanfile.conf.get("tools.apple.xcodebuild:verbosity", default="", check_type=str)
        if verbosity == "quiet" or verbosity == "verbose":
            return "-{}".format(verbosity)
        elif verbosity:
            raise ConanException("Value {} for 'tools.apple.xcodebuild:verbosity' is not valid".format(verbosity))
        return ""

    @property
    def _sdkroot(self):
        # User's sdk_path has priority, then if specified try to compose sdk argument
        # with sdk/sdk_version settings, leave blank otherwise and the sdk will be automatically
        # chosen by the build system
        sdk = self._conanfile.conf.get("tools.apple:sdk_path")
        if not sdk and self._sdk:
            sdk = "{}{}".format(self._sdk, self._sdk_version)
        return "SDKROOT={}".format(sdk) if sdk else ""

    def build(self, xcodeproj, target=None):
        """
        Call to ``xcodebuild`` to build a Xcode project.

        :param xcodeproj: the *xcodeproj* file to build.
        :param target: the target to build, in case this argument is passed to the ``build()``
                       method it will add the ``-target`` argument to the build system call. If not passed, it
                       will build all the targets passing the ``-alltargets`` argument instead.
        :return: the return code for the launched ``xcodebuild`` command.
        """
        target = "-target {}".format(target) if target else "-alltargets"
        cmd = "xcodebuild -project {} -configuration {} -arch {} " \
              "{} {} {}".format(xcodeproj, self._build_type, self._arch, self._sdkroot,
                                self._verbosity, target)
        self._conanfile.run(cmd)
