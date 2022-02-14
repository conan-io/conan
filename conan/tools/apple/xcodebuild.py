import os

from conan.tools.apple.apple import to_apple_arch
from conans.errors import ConanException


class XcodeBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_type = conanfile.settings.get_safe("build_type")
        self.arch = to_apple_arch(conanfile.settings.get_safe("arch"))

    @property
    def verbosity(self):
        verbosity = self._conanfile.conf["tools.apple.xcodebuild:verbosity"]
        if not verbosity:
            return ""
        elif verbosity == "quiet" or verbosity == "verbose":
            return "-{}".format(verbosity)
        else:
            raise ConanException("Value {} for 'tools.apple.xcodebuild:verbosity' is not valid".format(verbosity))

    def build(self, xcodeproj, use_xcconfig=True):
        # TODO: check if we want to pass conandeps.xcconfig or the xcodeproj is suposed to have
        #  it embedded inside
        xcconfig = " -xcconfig {}".format(
            os.path.join(self._conanfile.folders.generators,
                         "conandeps.xcconfig")) if use_xcconfig else ""
        cmd = "xcodebuild -project {}{} -configuration {} -arch {} {}".format(xcodeproj, xcconfig,
                                                                              self.build_type,
                                                                              self.arch,
                                                                              self.verbosity)
        self._conanfile.run(cmd)
