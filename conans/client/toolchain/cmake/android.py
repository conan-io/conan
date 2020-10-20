import textwrap

from .base import CMakeToolchainBase


class CMakeAndroidToolchain(CMakeToolchainBase):
    _toolchain_tpl = textwrap.dedent("""
        {% extends 'base_toolchain' %}

        {% block main %}
            {% if shared_libs -%}
            message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS= {{ shared_libs }}")
            set(BUILD_SHARED_LIBS {{ shared_libs }})
            {%- endif %}

            {% if parallel -%}
            set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ parallel }}")
            set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ parallel }}")
            {%- endif %}

            {% if cppstd -%}
            message(STATUS "Conan C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}}")
            set(CMAKE_CXX_STANDARD {{ cppstd }})
            set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
            {%- endif %}
        {% endblock %}

        {% block footer %}
            set(CMAKE_CXX_FLAGS_INIT "${CONAN_CXX_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_C_FLAGS_INIT "${CONAN_C_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CONAN_SHARED_LINKER_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_EXE_LINKER_FLAGS_INIT "${CONAN_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)
        {% endblock %}
    """)

    # TODO: fPIC, fPIE
    # TODO: RPATH, cross-compiling to Android?
    # TODO: libcxx, only libc++ https://developer.android.com/ndk/guides/cpp-support

    def __init__(self, conanfile, build_type=None, **kwargs):
        super(CMakeAndroidToolchain, self).__init__(conanfile, build_type=build_type, **kwargs)
        self.build_type = build_type or self._conanfile.settings.get_safe("build_type")

    def _get_templates(self):
        templates = super(CMakeAndroidToolchain, self)._get_templates()
        templates.update({
            CMakeToolchainBase.filename: self._toolchain_tpl,
        })
        return templates

    def _get_android_abi(self):
        return {"x86": "x86",
                "x86_64": "x86_64",
                "armv7": "armeabi-v7a",
                "armv8": "arm64-v8a"}.get(str(self._conanfile.settings.arch))

    def _get_android_stl(self):
        libcxx_str = str(self._conanfile.settings.compiler.libcxx)
        return libcxx_str  # TODO: only 'c++_shared' y 'c++_static' supported?

    def _get_template_context_data(self):
        ctxt_toolchain, _ = super(CMakeAndroidToolchain, self)._get_template_context_data()
        ctxt_toolchain.update({
            'CMAKE_SYSTEM_NAME': 'Android',
            'CMAKE_SYSTEM_VERSION': self._conanfile.settings.os.api_level,
            'CMAKE_ANDROID_ARCH_ABI': self._get_android_abi(),
            'CMAKE_ANDROID_STL_TYPE': self._get_android_stl()
            'CMAKE_ANDROID_NDK': '/Users/jgsogo/Library/Android/sdk/ndk/21.0.6113669',  # TODO: ???

        })
        return ctxt_toolchain, {}
