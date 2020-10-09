import textwrap

from .base import CMakeToolchainBase


class CMakeiOSToolchain(CMakeToolchainBase):
    _template_project_include = ''  # TODO: This file is not useful to Android, there is no MSVC runtime MD/MT

    # TODO: Factorize with the native one
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

        set(CONAN_SETTINGS_HOST_ARCH "arm64")
        set(CONAN_SETTINGS_HOST_OS "iOS") # CMAKE_SYSTEM_NAME
        set(CONAN_SETTINGS_HOST_OS_VERSION "12.0") # SDK_VERSION

        # TODO: add logic to calc the deployment target
        set(CONAN_SETTINGS_HOST_MIN_OS_VERSION "9.0") # DEPLOYMENT TARGET

        set(CMAKE_SYSTEM_NAME ${CONAN_SETTINGS_HOST_OS})

        # calc sdk based on host_os
        set(CONAN_SDK_NAME "iphonesimulator")

        set(CONAN_SDK_VERSION ${CONAN_SETTINGS_HOST_OS_VERSION})

        set(DEPLOYMENT_TARGET ${CONAN_SETTINGS_HOST_MIN_OS_VERSION})


        # Set the architectures for which to build.
        set(CMAKE_OSX_ARCHITECTURES ${CONAN_SETTINGS_HOST_ARCH})
        set(CMAKE_OSX_SYSROOT "${CONAN_SDK_NAME}")

        # Setting CMAKE_OSX_SYSROOT SDK, when using Xcode generator the name is enough
        # but full path is necessary for others
        set(CMAKE_OSX_SYSROOT "${CONAN_SDK_NAME}" CACHE INTERNAL "")
        if(NOT DEFINED CMAKE_XCODE_ATTRIBUTE_DEVELOPMENT_TEAM)
          set(CMAKE_XCODE_ATTRIBUTE_DEVELOPMENT_TEAM "123456789A" CACHE INTERNAL "")
        endif()


    """)

    def __init__(self, conanfile, build_type=None, **kwargs):
        super(CMakeiOSToolchain, self).__init__(conanfile, build_type=build_type, **kwargs)
        self.build_type = build_type or self._conanfile.settings.get_safe("build_type")

    def get_architecture(self):
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

    def get_sdk_name(self):
        os_name = self._conanfile.settings.get_safe("os")
        return {"iOS": "iphoneos",
                "watchOS": "appletvos",
                "tvOS": "watchos"}.get(os_name)
        return None
