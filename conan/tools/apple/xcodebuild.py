import os

from conan.tools.apple.apple import to_apple_arch
from conans.errors import ConanException


class XcodeBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_type = conanfile.settings.get_safe("build_type")
        self.arch = to_apple_arch(conanfile.settings.get_safe("arch"))
        self.sdk = conanfile.settings.get_safe("os.sdk") or ""
        self.sdk_version = conanfile.settings.get_safe("os.sdk_version") or ""
        self.os_version = conanfile.settings.get_safe("os.version") or ""

    @property
    def verbosity(self):
        verbosity = self._conanfile.conf["tools.apple.xcodebuild:verbosity"]
        if not verbosity:
            return ""
        elif verbosity == "quiet" or verbosity == "verbose":
            return "-{}".format(verbosity)
        else:
            raise ConanException("Value {} for 'tools.apple.xcodebuild:verbosity' is not valid".format(verbosity))

    @property
    def sdkroot(self):
        # TODO: check if we want move this logic to tools
        # User's sdk_path has priority, then if specified try to compose sdk argument
        # with sdk/sdk_version settings, leave blank otherwise and the sdk will be automatically
        # chosen by the build system
        sdk = self._conanfile.conf["tools.apple:sdk_path"]
        if not sdk and self.sdk:
            sdk = "{}{}".format(self.sdk, self.sdk_version)
        return "SDKROOT={}".format(sdk) if sdk else ""

    # TODO: check this, apparently this is not working as it should
    #  https://pewpewthespells.com/blog/buildsettings.html#macosx_deployment_target
    #  it should set the -mmacosx-version-min=$(value) for clang but instead it modifies
    #  the -target argument but apparently it works in a very similar way???
    @property
    def deployment_target(self):
        return "MACOSX_DEPLOYMENT_TARGET={}".format(self.os_version) if self.os_version else ""

    def build(self, xcodeproj):
        cmd = "xcodebuild -project {} -configuration {} -arch " \
              "{} {} {} {}".format(xcodeproj, self.build_type, self.arch, self.sdkroot,
                                   self.verbosity, self.deployment_target)
        self._conanfile.run(cmd)
