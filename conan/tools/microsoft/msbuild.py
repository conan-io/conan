from conan.tools.microsoft.visual import vcvars_arch, vcvars_command
from conans.client.tools import intel_compilervars_command
from conans.errors import ConanException


def msbuild_verbosity_cmd_line_arg(conanfile):
    verbosity = conanfile.conf["tools.microsoft"].msbuild_verbosity
    if verbosity:
        if verbosity not in ("Quiet", "Minimal", "Normal", "Detailed", "Diagnostic"):
            raise ConanException("Unknown msbuild verbosity: {}".format(verbosity))
        return '/verbosity:{}'.format(verbosity)


class MSBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.compiler = conanfile.settings.get_safe("compiler")
        # This is assuming this is the Visual Studio IDE version, used for the vcvars
        self.version = (conanfile.settings.get_safe("compiler.base.version") or
                        conanfile.settings.get_safe("compiler.version"))
        if self.compiler == "msvc":
            version = self.version[:4]  # Remove the latest version number 19.1X if existing
            _visuals = {'19.0': '14',  # TODO: This is common to CMake, refactor
                        '19.1': '15',
                        '19.2': '16'}
            self.version = _visuals[version]
        self.vcvars_arch = vcvars_arch(conanfile)
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
        if self.compiler == "intel":
            cvars = intel_compilervars_command(self._conanfile)
        else:
            cvars = vcvars_command(self.version, architecture=self.vcvars_arch,
                                   platform_type=None, winsdk_version=None,
                                   vcvars_ver=None)
        cmd = ('%s && msbuild "%s" /p:Configuration=%s /p:Platform=%s'
               % (cvars, sln, self.build_type, self.platform))

        verbosity = msbuild_verbosity_cmd_line_arg(self._conanfile)
        if verbosity:
            cmd += " {}".format(verbosity)

        return cmd

    def build(self, sln):
        cmd = self.command(sln)
        self._conanfile.run(cmd)

    @staticmethod
    def get_version(_):
        return NotImplementedError("get_version() method is not supported in MSBuild "
                                   "toolchain helper")
