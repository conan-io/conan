import os

from conans.errors import ConanException


def msbuild_verbosity_cmd_line_arg(conanfile):
    verbosity = conanfile.conf["tools.microsoft.msbuild"].verbosity
    if verbosity:
        if verbosity not in ("Quiet", "Minimal", "Normal", "Detailed", "Diagnostic"):
            raise ConanException("Unknown msbuild verbosity: {}".format(verbosity))
        return '/verbosity:{}'.format(verbosity)


def msbuild_max_cpu_count_cmd_line_arg(conanfile):
    max_cpu_count = conanfile.conf["tools.microsoft.msbuild"].max_cpu_count or \
                    conanfile.conf["tools.build"].processes
    if max_cpu_count:
        return "/m:{}".format(max_cpu_count)


class MSBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_type = conanfile.settings.get_safe("build_type")
        msvc_arch = {'x86': 'x86',
                     'x86_64': 'x64',
                     'armv7': 'ARM',
                     'armv8': 'ARM64'}
        # if platforms:
        #    msvc_arch.update(platforms)
        arch = conanfile.settings.get_safe("arch")
        msvc_arch = msvc_arch.get(str(arch))
        if conanfile.settings.get_safe("os") == "WindowsCE":
            msvc_arch = conanfile.settings.get_safe("os.platform")
        self.platform = msvc_arch

    def command(self, sln):
        cmd = ('msbuild "%s" /p:Configuration=%s /p:Platform=%s'
               % (sln, self.build_type, self.platform))

        verbosity = msbuild_verbosity_cmd_line_arg(self._conanfile)
        if verbosity:
            cmd += " {}".format(verbosity)

        max_cpu_count = msbuild_max_cpu_count_cmd_line_arg(self._conanfile)
        if max_cpu_count:
            cmd += " {}".format(max_cpu_count)

        return cmd

    def build(self, sln):
        cmd = self.command(sln)
        vcvars = os.path.join(self._conanfile.install_folder, "conanvcvars")
        self._conanfile.run(cmd, env=["conanbuildenv", vcvars])

    @staticmethod
    def get_version(_):
        return NotImplementedError("get_version() method is not supported in MSBuild "
                                   "toolchain helper")
