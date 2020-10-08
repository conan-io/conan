import textwrap

from .base import CMakeToolchainBase


class CMakeAndroidToolchain(CMakeToolchainBase):
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

        # Parallel builds
        {% if parallel -%}
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ parallel }}")
        set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ parallel }}")
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

        # Variables
        {% for it, value in variables.items() -%}
        set({{ it }} "{{ value }}")
        {% endfor %}
        # Variables  per configuration
        {% for it, values in variables_config.items() -%}
            {%- set genexpr = namespace(str='') %}
            {%- for conf, value in values -%}
                {%- set genexpr.str = genexpr.str +
                                      '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                {%- if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
            {%- endfor -%}
            {% for i in range(values|count) %}{%- set genexpr.str = genexpr.str + '>' %}
            {%- endfor -%}
        set({{ it }} {{ genexpr.str }})
        {% endfor %}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() -%}
        # add_compile_definitions only works in cmake >= 3.12
        add_definitions(-D{{ it }}="{{ value }}")
        {% endfor %}
        # Preprocessor definitions per configuration
        {% for it, values in preprocessor_definitions_config.items() -%}
            {%- set genexpr = namespace(str='') %}
            {%- for conf, value in values -%}
                {%- set genexpr.str = genexpr.str +
                                      '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                {%- if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
            {%- endfor -%}
            {% for i in range(values|count) %}{%- set genexpr.str = genexpr.str + '>' %}
            {%- endfor -%}
        add_definitions(-D{{ it }}={{ genexpr.str }})
        {% endfor %}
    """)

    # TODO: fPIC, fPIE
    # TODO: RPATH, cross-compiling to Android?
    # TODO: libcxx, only libc++ https://developer.android.com/ndk/guides/cpp-support

    def __init__(self, build_type=None, **kwargs):
        super(CMakeAndroidToolchain, self).__init__(build_type=build_type, **kwargs)
        # TODO: Is this abuse of 'variables' attribute?
        self.variables['CMAKE_SYSTEM_NAME'] = 'Android'
        self.variables['CMAKE_SYSTEM_VERSION'] = self._conanfile.settings.os.api_level
        self.variables['CMAKE_ANDROID_ARCH_ABI'] = self._get_android_abi()
        self.variables[
            'CMAKE_ANDROID_NDK'] = '/Users/jgsogo/Library/Android/sdk/ndk/21.0.6113669'  # TODO: ???
        self.variables['CMAKE_ANDROID_STL_TYPE'] = self._get_android_stl()

        self.build_type = build_type or self._conanfile.settings.get_safe("build_type")

    def _get_android_abi(self):
        return {"x86": "x86",
                "x86_64": "x86_64",
                "armv7": "armeabi-v7a",
                "armv8": "arm64-v8a"}.get(str(self._conanfile.settings.arch))

    def _get_android_stl(self):
        libcxx_str = str(self._conanfile.settings.compiler.libcxx)
        return libcxx_str  # TODO: only 'c++_shared' y 'c++_static' supported?
