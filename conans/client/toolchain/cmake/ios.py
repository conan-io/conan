import textwrap

from .base import CMakeToolchainBase


class CMakeiOSToolchain(CMakeToolchainBase):
    _template_project_include = ''

    _template_toolchain = textwrap.dedent("""
        # Conan automatically generated toolchain file
        # DO NOT EDIT MANUALLY, it will be overwritten
        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED TRUE)
        # build_type (Release, Debug, etc) is only defined for single-config generators
        {%- if build_type %}
        set(CMAKE_BUILD_TYPE "{{ build_type }}" CACHE STRING "Choose the type of build." FORCE)
        {%- endif %}
        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(_CMAKE_IN_TRY_COMPILE)
            message(STATUS "Running toolchain IN_TRY_COMPILE")
            return()
        endif()
        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")
        # We are going to adjust automagically many things as requested by Conan
        #   these are the things done by 'conan_basic_setup()'
        set(CMAKE_EXPORT_NO_PACKAGE_REGISTRY ON)
        # To support the cmake_find_package generators
        {% if cmake_module_path -%}
        set(CMAKE_MODULE_PATH {{ cmake_module_path }} ${CMAKE_MODULE_PATH})
        {%- endif %}
        {% if cmake_prefix_path -%}
        set(CMAKE_PREFIX_PATH {{ cmake_prefix_path }} ${CMAKE_PREFIX_PATH})
        {%- endif %}
        # shared libs
        {% if shared_libs -%}
        message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS= {{ shared_libs }}")
        set(BUILD_SHARED_LIBS {{ shared_libs }})
        {%- endif %}

        # C++ Standard
        {% if cppstd -%}
        message(STATUS "Conan C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}}")
        set(CMAKE_CXX_STANDARD {{ cppstd }})
        set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
        {%- endif %}
        # Install prefix
        {% if install_prefix -%}
        set(CMAKE_INSTALL_PREFIX "{{install_prefix}}" CACHE STRING "" FORCE)
        {%- endif %}

        # iOS stuff
        # conan vars
        set(CONAN_SETTINGS_HOST_ARCH "{{host_architecture}}")
        set(CONAN_SETTINGS_HOST_OS "{{host_os}}") # CMAKE_SYSTEM_NAME
        set(CONAN_SETTINGS_HOST_OS_VERSION "{{host_os_version}}") # SDK_VERSION
        set(CONAN_SDK_NAME "{{host_sdk_name}}")

        # set cmake vars
        set(CMAKE_SYSTEM_NAME ${CONAN_SETTINGS_HOST_OS})
        set(CMAKE_SYSTEM_VERSION ${CONAN_SETTINGS_HOST_OS_VERSION})
        set(DEPLOYMENT_TARGET ${CONAN_SETTINGS_HOST_MIN_OS_VERSION})
        # Set the architectures for which to build.
        set(CMAKE_OSX_ARCHITECTURES ${CONAN_SETTINGS_HOST_ARCH})
        # Setting CMAKE_OSX_SYSROOT SDK, when using Xcode generator the name is enough
        # but full path is necessary for others
        set(CMAKE_OSX_SYSROOT "${CONAN_SDK_NAME}")
        if(NOT DEFINED CMAKE_XCODE_ATTRIBUTE_DEVELOPMENT_TEAM)
          set(CMAKE_XCODE_ATTRIBUTE_DEVELOPMENT_TEAM "123456789A" CACHE INTERNAL "")
        endif()
    """)

    def __init__(self, conanfile, build_type=None, **kwargs):
        super(CMakeiOSToolchain, self).__init__(conanfile, build_type=build_type, **kwargs)
        self.build_type = build_type or self._conanfile.settings.get_safe("build_type")
        self.host_architecture = self._get_architecture()
        self.host_os = self._conanfile.settings.get_safe("os")
        self.host_os_version = self._conanfile.settings.get_safe("os.version")
        self.host_sdk_name = self._get_sdk_name(self.host_architecture)
        self.libcxx = self._conanfile.settings.get_safe("compiler.libcxx")
        self.cppstd = self._conanfile.settings.get_safe("compiler.cppstd")

        #TODO: Discuss how to handle CMAKE_OSX_DEPLOYMENT_TARGET to set min-version
        #add a setting? check an option and if not present set a default?
        #default to os.version?

        try:
            # This is only defined in the cache, not in the local flow
            self.install_prefix = self._conanfile.package_folder.replace("\\", "/")
        except AttributeError:
            # FIXME: In the local flow, we don't know the package_folder
            self.install_prefix = None

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
        return None

    def _get_sdk_name(self, architecture):
        os_name = self._conanfile.settings.get_safe("os")
        if "arm" in architecture:
            return {"iOS": "iphoneos",
                    "watchOS": "appletvos",
                    "tvOS": "watchos"}.get(os_name)
        else:
            return {"iOS": "iphonesimulator",
                    "watchOS": "appletvsimulator",
                    "tvOS": "watchsimulator"}.get(os_name)
        return None

    def _get_template_context_data(self):
        tpl_toolchain_context, tpl_project_include_context = \
            super(CMakeiOSToolchain, self)._get_template_context_data()
        tpl_toolchain_context.update({
            "host_architecture": self.host_architecture,
            "host_os": self.host_os,
            "host_os_version": self.host_os_version,
            "host_sdk_name": self.host_sdk_name,
            "install_prefix": self.install_prefix,
            "set_libcxx": self.libcxx,
            "cppstd": self.cppstd
        })
        return tpl_toolchain_context, tpl_project_include_context
