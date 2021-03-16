import textwrap

from conan.tools.cmake.base import CMakeToolchainBase


class CMakeiOSToolchain(CMakeToolchainBase):
    _toolchain_tpl = textwrap.dedent("""
        {% extends 'base_toolchain' %}
        {% block before_try_compile %}
            {{ super() }}
            # set cmake vars
            set(CMAKE_SYSTEM_NAME {{ CMAKE_SYSTEM_NAME }})
            set(CMAKE_SYSTEM_VERSION {{ CMAKE_SYSTEM_VERSION }})
            set(DEPLOYMENT_TARGET ${CONAN_SETTINGS_HOST_MIN_OS_VERSION})
            # Set the architectures for which to build.
            set(CMAKE_OSX_ARCHITECTURES {{ CMAKE_OSX_ARCHITECTURES }})
            # Setting CMAKE_OSX_SYSROOT SDK, when using Xcode generator the name is enough
            # but full path is necessary for others
            set(CMAKE_OSX_SYSROOT {{ CMAKE_OSX_SYSROOT }})
        {% endblock %}
    """)

    def __init__(self, conanfile, build_type=None, **kwargs):
        super(CMakeiOSToolchain, self).__init__(conanfile, build_type=build_type, **kwargs)
        self.build_type = build_type or self._conanfile.settings.get_safe("build_type")
        self.host_architecture = self._get_architecture()
        self.host_os = self._conanfile.settings.get_safe("os")
        self.host_os_version = self._conanfile.settings.get_safe("os.version")
        self.host_sdk_name = self._apple_sdk_name()

        # TODO: Discuss how to handle CMAKE_OSX_DEPLOYMENT_TARGET to set min-version
        # add a setting? check an option and if not present set a default?
        # default to os.version?

    def _get_templates(self):
        templates = super(CMakeiOSToolchain, self)._get_templates()
        templates.update({
            CMakeToolchainBase.filename: self._toolchain_tpl,
        })
        return templates

    def _get_architecture(self):
        # check valid combinations of architecture - os ?
        # for iOS a FAT library valid for simulator and device
        # can be generated if multiple archs are specified:
        # "-DCMAKE_OSX_ARCHITECTURES=armv7;armv7s;arm64;i386;x86_64"
        arch = self._conanfile.settings.get_safe("arch")
        return {"x86": "i386",
                "x86_64": "x86_64",
                "armv8": "arm64",
                "armv8_32": "arm64_32"}.get(arch, arch)

    # TODO: refactor, comes from conans.client.tools.apple.py
    def _apple_sdk_name(self):
        """returns proper SDK name suitable for OS and architecture
        we're building for (considering simulators)"""
        arch = self._conanfile.settings.get_safe('arch')
        os_ = self._conanfile.settings.get_safe('os')
        if str(arch).startswith('x86'):
            return {'Macos': 'macosx',
                    'iOS': 'iphonesimulator',
                    'watchOS': 'watchsimulator',
                    'tvOS': 'appletvsimulator'}.get(str(os_))
        else:
            return {'Macos': 'macosx',
                    'iOS': 'iphoneos',
                    'watchOS': 'watchos',
                    'tvOS': 'appletvos'}.get(str(os_), None)

    def _get_template_context_data(self):
        ctxt_toolchain = super(CMakeiOSToolchain, self)._get_template_context_data()
        ctxt_toolchain.update({
            "CMAKE_OSX_ARCHITECTURES": self.host_architecture,
            "CMAKE_SYSTEM_NAME": self.host_os,
            "CMAKE_SYSTEM_VERSION": self.host_os_version,
            "CMAKE_OSX_SYSROOT": self.host_sdk_name
        })
        return ctxt_toolchain
