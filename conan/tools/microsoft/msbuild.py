from conans.client.tools.oss import cpu_count
from conans.errors import ConanException


def msbuild_verbosity_cmd_line_arg(conanfile):
    verbosity = conanfile.conf["tools.microsoft.msbuild"].verbosity
    if verbosity:
        if verbosity not in ("Quiet", "Minimal", "Normal", "Detailed", "Diagnostic"):
            raise ConanException("Unknown msbuild verbosity: {}".format(verbosity))
        return '/verbosity:{}'.format(verbosity)


def msbuild_max_cpu_count_cmd_line_arg(conanfile):
    max_cpu_count = conanfile.conf["tools.microsoft.msbuild"].maxCpuCount or \
                    conanfile.conf["core.build"].processes or \
                    cpu_count(output=conanfile.output)
    return "/m:{}".format(max_cpu_count)


class MSBuild(object):
    def __init__(self, conanfile, parallel=True):
        self._conanfile = conanfile
        self._parallel = parallel
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
        install_folder = self._conanfile.install_folder
        cmd = ('%s/conanvcvars.bat && msbuild "%s" /p:Configuration=%s /p:Platform=%s'
               % (install_folder, sln, self.build_type, self.platform))

        verbosity = msbuild_verbosity_cmd_line_arg(self._conanfile)
        if verbosity:
            cmd += " {}".format(verbosity)

        if self._parallel:
            cmd += " {}".format(msbuild_max_cpu_count_cmd_line_arg(self._conanfile))

        return cmd

    def build(self, sln):
        cmd = self.command(sln)
        self._conanfile.run(cmd)

    @staticmethod
    def get_version(_):
        return NotImplementedError("get_version() method is not supported in MSBuild "
                                   "toolchain helper")
