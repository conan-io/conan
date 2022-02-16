import textwrap

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.apple.apple import to_apple_arch
from conans.util.files import save


class XcodeToolchain(object):
    filename = "conantoolchain"
    extension = ".xcconfig"

    _vars_xconfig = textwrap.dedent("""\
        // Definition of toolchain variables
        {macosx_deployment_target}
        {clang_cxx_library}
        {clang_cxx_language_standard}
        """)

    _all_xconfig = textwrap.dedent("""\
        // Conan XcodeToolchain generated file
        // Includes all installed configurations
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        arch = conanfile.settings.get_safe("arch")
        self.architecture = to_apple_arch(arch) or arch
        self.build_type = conanfile.settings.build_type
        self.sdk = conanfile.settings.get_safe("os.sdk")
        self.sdk_version = conanfile.settings.get_safe("os.sdk_version")
        self.libcxx = conanfile.settings.get_safe("compiler.libcxx")
        self.cppstd = conanfile.settings.get_safe("compiler.cppstd")
        self.fpic = conanfile.options.get_safe("fPIC")
        self.os_version = conanfile.settings.get_safe("os.version")
        check_using_build_profile(self._conanfile)

    @property
    def _sdk_condition(self):
        if self.sdk:
            sdk = "{}{}".format(self.sdk, self.sdk_version or "*")
            return sdk
        return "*"

    @property
    def _var_condition(self):
        return "[config={}][arch={}][sdk={}]".format(self.build_type, self.architecture,
                                                     self._sdk_condition)

    @property
    def macosx_deployment_target(self):
        return "MACOSX_DEPLOYMENT_TARGET{}={}".format(self._var_condition,
                                                      self.os_version) if self.os_version else ""

    @property
    def clang_cxx_library(self):
        return "CLANG_CXX_LIBRARY{}={}".format(self._var_condition, self.libcxx) if self.libcxx else ""

    @property
    def clang_cxx_language_standard(self):
        return "CLANG_CXX_LANGUAGE_STANDARD{}={}".format(self._var_condition, self.cppstd) if self.cppstd else ""

    @property
    def sdkroot(self):
        # TODO: check if we want move this logic to tools
        # User's sdk_path has priority, then if specified try to compose sdk argument
        # with sdk/sdk_version settings, leave blank otherwise and the sdk will be automatically
        # chosen by the build system
        sdk = self._conanfile.conf["tools.apple:sdk_path"]
        if not sdk and self.sdk:
            sdk = "{}{}".format(self.sdk, self.sdk_version or "")
        return "SDKROOT={}".format(sdk) if sdk else ""

    @property
    def archs(self):
        return "ARCHS={}".format(self.architecture)

    @property
    def configuration(self):
        return "CONFIGURATION={}".format(self.build_type)

    @property
    def _vars_xconfig_filename(self):
        props = [("configuration", self.build_type),
                 ("architecture", self.architecture),
                 ("sdk name", self.sdk),
                 ("sdk version", self.sdk_version)]
        name = "".join("_{}".format(v) for _, v in props if v is not None and v)
        name = name.replace(".", "_").replace("-", "_")
        return self.filename + name.lower() + self.extension

    @property
    def _all_xconfig_filename(self):
        return self.filename + self.extension

    @property
    def _vars_xconfig_content(self):
        ret = self._vars_xconfig.format(sdkroot=self.sdkroot,
                                        archs=self.archs,
                                        configuration=self.configuration,
                                        macosx_deployment_target=self.macosx_deployment_target,
                                        clang_cxx_library=self.clang_cxx_library,
                                        clang_cxx_language_standard=self.clang_cxx_language_standard)
        return ret

    @property
    def _all_xconfig_content(self):
        return ""

    def generate(self):
        save(self._all_xconfig_filename, self._all_xconfig_content)
        save(self._vars_xconfig_filename, self._vars_xconfig_content)
