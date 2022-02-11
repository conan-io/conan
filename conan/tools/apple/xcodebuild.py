from conan.tools.apple.apple import to_apple_arch
from conans.errors import ConanException


class XcodeBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_type = conanfile.settings.get_safe("build_type")
        arch = conanfile.settings.get_safe("arch")
        xcode_arch = to_apple_arch(arch)
        if conanfile.settings.get_safe("os") == "WindowsCE":
            xcode_arch = conanfile.settings.get_safe("os.platform")
        self.platform = xcode_arch

    def command(self, sln):
        cmd = ('xcodebuild "%s" /p:Configuration=%s /p:Platform=%s'
               % (sln, self.build_type, self.platform))

        verbosity = xcodebuild_verbosity_cmd_line_arg(self._conanfile)
        if verbosity:
            cmd += " {}".format(verbosity)

        maxcpucount = self._conanfile.conf["tools.microsoft.xcodebuild:max_cpu_count"]
        if maxcpucount:
            cmd += " /m:{}".format(maxcpucount)

        return cmd

    def build(self, sln):
        cmd = self.command(sln)
        self._conanfile.run(cmd)

    @staticmethod
    def get_version(_):
        return NotImplementedError("get_version() method is not supported in xcodebuild "
                                   "toolchain helper")
