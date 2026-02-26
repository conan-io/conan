import textwrap

import jinja2
from jinja2 import Template

from conan.errors import ConanException


class ConfigVersionTemplate2:
    """
    foo-config-version.cmake
    """
    def __init__(self, cmakedeps, conanfile):
        self._cmakedeps = cmakedeps
        self._conanfile = conanfile

    def content(self):
        ret = {}
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        for config_comp_name, cmake_file_name in self._cmakedeps.get_cmake_filenames(self._conanfile).items():
            context = self._get_context(config_comp_name, cmake_file_name)
            filename = f"{cmake_file_name}-config-version.cmake" if cmake_file_name == cmake_file_name.lower() \
                else f"{cmake_file_name}ConfigVersion.cmake"
            ret[filename] = t.render(context)
        return ret

    def _get_context(self, config_comp_name, cmake_file_name):
        policy = self._cmakedeps.get_property("cmake_config_version_compat", self._conanfile,
                                              comp_name=config_comp_name)
        if policy is None:
            policy = "SameMajorVersion"
        if policy not in ("AnyNewerVersion", "SameMajorVersion", "SameMinorVersion", "ExactVersion"):
            raise ConanException(f"Unknown cmake_config_version_compat={policy} in {self._conanfile}")
        version = (self._cmakedeps.get_property("system_package_version", self._conanfile, comp_name=config_comp_name) or
                   self._conanfile.ref.version)
        return {"version": version,
                "policy": policy}

    @property
    def _template(self):
        # https://gitlab.kitware.com/cmake/cmake/blob/master/Modules/BasicConfigVersion-SameMajorVersion.cmake.in
        # This will be at XXX-config-version.cmake
        # AnyNewerVersion|SameMajorVersion|SameMinorVersion|ExactVersion
        ret = textwrap.dedent("""\
            set(PACKAGE_VERSION "{{ version }}")

            if(PACKAGE_VERSION VERSION_LESS PACKAGE_FIND_VERSION)
                set(PACKAGE_VERSION_COMPATIBLE FALSE)
            else()
                {% if policy == "AnyNewerVersion" %}
                set(PACKAGE_VERSION_COMPATIBLE TRUE)
                {% elif policy == "SameMajorVersion" %}
                if("{{ version }}" MATCHES "^([0-9]+)\\\\.")
                    set(CVF_VERSION_MAJOR {{ '${CMAKE_MATCH_1}' }})
                else()
                    set(CVF_VERSION_MAJOR "{{ version }}")
                endif()

                if(PACKAGE_FIND_VERSION_MAJOR STREQUAL CVF_VERSION_MAJOR)
                    set(PACKAGE_VERSION_COMPATIBLE TRUE)
                else()
                    set(PACKAGE_VERSION_COMPATIBLE FALSE)
                endif()
                {% elif policy == "SameMinorVersion" %}
                if("{{ version }}" MATCHES "^([0-9]+)\\.([0-9]+)")
                    set(CVF_VERSION_MAJOR "${CMAKE_MATCH_1}")
                    set(CVF_VERSION_MINOR "${CMAKE_MATCH_2}")
                else()
                    set(CVF_VERSION_MAJOR "{{ version }}")
                    set(CVF_VERSION_MINOR "")
                endif()
                if((PACKAGE_FIND_VERSION_MAJOR STREQUAL CVF_VERSION_MAJOR) AND
                    (PACKAGE_FIND_VERSION_MINOR STREQUAL CVF_VERSION_MINOR))
                  set(PACKAGE_VERSION_COMPATIBLE TRUE)
                else()
                  set(PACKAGE_VERSION_COMPATIBLE FALSE)
                endif()
                {% elif policy == "ExactVersion" %}
                if("{{ version }}" MATCHES "^([0-9]+)\\.([0-9]+)\\.([0-9]+)")
                    set(CVF_VERSION_MAJOR "${CMAKE_MATCH_1}")
                    set(CVF_VERSION_MINOR "${CMAKE_MATCH_2}")
                    set(CVF_VERSION_MINOR "${CMAKE_MATCH_3}")
                else()
                    set(CVF_VERSION_MAJOR "{{ version }}")
                    set(CVF_VERSION_MINOR "")
                    set(CVF_VERSION_PATCH "")
                endif()
                if((PACKAGE_FIND_VERSION_MAJOR STREQUAL CVF_VERSION_MAJOR) AND
                    (PACKAGE_FIND_VERSION_MINOR STREQUAL CVF_VERSION_MINOR) AND
                    (PACKAGE_FIND_VERSION_PATCH STREQUAL CVF_VERSION_PATCH))
                  set(PACKAGE_VERSION_COMPATIBLE TRUE)
                else()
                  set(PACKAGE_VERSION_COMPATIBLE FALSE)
                endif()
                {% endif %}

                if(PACKAGE_FIND_VERSION STREQUAL PACKAGE_VERSION)
                    set(PACKAGE_VERSION_EXACT TRUE)
                endif()
            endif()
            """)
        return ret
