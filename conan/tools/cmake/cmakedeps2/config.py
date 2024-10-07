import textwrap


class ConfigTemplate2:
    """
    FooConfig.cmake
    foo-config.cmake
    """
    @property
    def filename(self):
        if self.file_name == self.file_name.lower():
            return "{}-config.cmake".format(self.file_name)
        else:
            return "{}Config.cmake".format(self.file_name)

    @property
    def context(self):
        targets_include = "" if not self.generating_module else "module-"
        targets_include += "{}Targets.cmake".format(self.file_name)
        return {"is_module": self.generating_module,
                "version": self.conanfile.ref.version,
                "file_name":  self.file_name,
                "pkg_name": self.pkg_name,
                "config_suffix": self.config_suffix,
                "targets_include_file": targets_include}

    @property
    def template(self):
        return textwrap.dedent("""\
        {%- macro pkg_var(pkg_name, var, config_suffix) -%}
             {{'${'+pkg_name+'_'+var+config_suffix+'}'}}
        {%- endmacro -%}
        ########## MACROS ###########################################################################
        #############################################################################################

        # Requires CMake > 3.15
        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/{{ targets_include_file }})
        include(CMakeFindDependencyMacro)

        check_build_type_defined()

        foreach(_DEPENDENCY {{ pkg_var(pkg_name, 'FIND_DEPENDENCY_NAMES', '') }} )
            # Check that we have not already called a find_package with the transitive dependency
            if(NOT {{ '${_DEPENDENCY}' }}_FOUND)
                find_dependency({{ '${_DEPENDENCY}' }} REQUIRED ${${_DEPENDENCY}_FIND_MODE})
            endif()
        endforeach()
        """)
