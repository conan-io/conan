import os

from conan.tools.apple.apple import to_apple_arch


class XcodeBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_type = conanfile.settings.get_safe("build_type")
        self.arch = to_apple_arch(conanfile.settings.get_safe("arch"))

    def build(self, xcodeproj, use_xcconfig=True):
        # TODO: check if we want to pass conandeps.xcconfig or the xcodeproj is suposed to have
        #  it embedded inside
        xcconfig = " -xcconfig {}".format(
            os.path.join(self._conanfile.folders.generators, "conandeps.xcconfig")) if use_xcconfig else ""
        cmd = "xcodebuild -project {}{} -configuration {} -arch {}".format(xcodeproj, xcconfig,
                                                                           self.build_type,
                                                                           self.arch)
        self._conanfile.run(cmd)
