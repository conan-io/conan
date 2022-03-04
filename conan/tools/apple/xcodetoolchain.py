import textwrap

from conan.tools.apple.apple import to_apple_arch
from conan.tools.apple.xcodedeps import GLOBAL_XCCONFIG_FILENAME, GLOBAL_XCCONFIG_TEMPLATE, \
    _add_include_to_file_or_create, _xcconfig_settings_filename, _xcconfig_conditional
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

    _agreggated_xconfig = textwrap.dedent("""\
        // Conan XcodeToolchain generated file
        // Includes all installed configurations

        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        arch = conanfile.settings.get_safe("arch")
        self.architecture = to_apple_arch(arch) or arch
        self.configuration = conanfile.settings.build_type
        self.libcxx = conanfile.settings.get_safe("compiler.libcxx")
        self.os_version = conanfile.settings.get_safe("os.version")

    def generate(self):
        save(GLOBAL_XCCONFIG_FILENAME, self._global_xconfig_content)
        save(self._agreggated_xconfig_filename, self._agreggated_xconfig_content)
        save(self._vars_xconfig_filename, self._vars_xconfig_content)

    @property
    def _cppstd(self):
        from conan.tools.build.flags import cppstd_flag
        cppstd = cppstd_flag(self._conanfile.settings)
        if cppstd.startswith("-std="):
            return cppstd[5:]
        return cppstd

    @property
    def _macosx_deployment_target(self):
        return 'MACOSX_DEPLOYMENT_TARGET{}={}'.format(_xcconfig_conditional(self._conanfile.settings),
                                                      self.os_version) if self.os_version else ""

    @property
    def _clang_cxx_library(self):
        return 'CLANG_CXX_LIBRARY{}={}'.format(_xcconfig_conditional(self._conanfile.settings),
                                               self.libcxx) if self.libcxx else ""

    @property
    def _clang_cxx_language_standard(self):
        return 'CLANG_CXX_LANGUAGE_STANDARD{}={}'.format(_xcconfig_conditional(self._conanfile.settings),
                                                         self._cppstd) if self._cppstd else ""
    @property
    def _vars_xconfig_filename(self):
        return "conantoolchain{}{}".format(_xcconfig_settings_filename(self._conanfile.settings),
                                                                       self.extension)

    @property
    def _vars_xconfig_content(self):
        ret = self._vars_xconfig.format(macosx_deployment_target=self._macosx_deployment_target,
                                        clang_cxx_library=self._clang_cxx_library,
                                        clang_cxx_language_standard=self._clang_cxx_language_standard)
        return ret

    @property
    def _agreggated_xconfig_content(self):
        return _add_include_to_file_or_create(self._agreggated_xconfig_filename,
                                              self._agreggated_xconfig,
                                              self._vars_xconfig_filename)

    @property
    def _global_xconfig_content(self):
        return _add_include_to_file_or_create(GLOBAL_XCCONFIG_FILENAME,
                                              GLOBAL_XCCONFIG_TEMPLATE,
                                              self._agreggated_xconfig_filename)

    @property
    def _agreggated_xconfig_filename(self):
        return self.filename + self.extension
