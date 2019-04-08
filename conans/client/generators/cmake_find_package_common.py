target_template = """
set({name}_INCLUDE_DIRS{build_type_suffix} {deps.include_paths})
set({name}_INCLUDES{build_type_suffix} {deps.include_paths})
set({name}_DEFINITIONS{build_type_suffix} {deps.defines})
set({name}_LINKER_FLAGS{build_type_suffix}_LIST "{deps.sharedlinkflags_list}" "{deps.exelinkflags_list}")  
set({name}_COMPILE_DEFINITIONS{build_type_suffix} {deps.compile_definitions})
set({name}_COMPILE_OPTIONS{build_type_suffix}_LIST "{deps.cxxflags_list}" "{deps.cflags_list}")
set({name}_LIBRARIES_TARGETS{build_type_suffix} "") # Will be filled later, if CMake 3
set({name}_LIBRARIES{build_type_suffix} "") # Will be filled later
set({name}_LIBS{build_type_suffix} "") # Same as {name}_LIBRARIES

mark_as_advanced({name}_INCLUDE_DIRS{build_type_suffix} 
                 {name}_INCLUDES{build_type_suffix}
                 {name}_DEFINITIONS{build_type_suffix}
                 {name}_LINKER_FLAGS{build_type_suffix}_LIST 
                 {name}_COMPILE_DEFINITIONS{build_type_suffix}
                 {name}_COMPILE_OPTIONS{build_type_suffix}_LIST
                 {name}_LIBRARIES{build_type_suffix} 
                 {name}_LIBS{build_type_suffix}
                 {name}_LIBRARIES_TARGETS{build_type_suffix})

# Find the real .lib/.a and add them to {name}_LIBS and {name}_LIBRARY_LIST
set({name}_LIBRARY_LIST{build_type_suffix} {deps.libs})
set({name}_LIB_DIRS{build_type_suffix} {deps.lib_paths})
foreach(_LIBRARY_NAME ${{{name}_LIBRARY_LIST{build_type_suffix}}})
    unset(CONAN_FOUND_LIBRARY CACHE)
    find_library(CONAN_FOUND_LIBRARY NAME ${{_LIBRARY_NAME}} PATHS ${{{name}_LIB_DIRS{build_type_suffix}}}
                 NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
    if(CONAN_FOUND_LIBRARY)
        list(APPEND {name}_LIBRARIES{build_type_suffix} ${{CONAN_FOUND_LIBRARY}})
        if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
            # Create a micro-target for each lib/a found
            set(_LIB_NAME CONAN_LIB::{name}_${{_LIBRARY_NAME}}{build_type_suffix})
            if(NOT TARGET ${{_LIB_NAME}})
                # Create a micro-target for each lib/a found
                add_library(${{_LIB_NAME}} UNKNOWN IMPORTED)
                set_target_properties(${{_LIB_NAME}} PROPERTIES IMPORTED_LOCATION ${{CONAN_FOUND_LIBRARY}})
            else()
                message(STATUS "Skipping already existing target: ${{_LIB_NAME}}")
            endif()
            list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_LIB_NAME}})
        endif()
        message(STATUS "Found: ${{CONAN_FOUND_LIBRARY}}")
    else()
        message(STATUS "Library ${{_LIBRARY_NAME}} not found in package, might be system one")
        list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_LIBRARY_NAME}})
        list(APPEND {name}_LIBRARIES{build_type_suffix} ${{_LIBRARY_NAME}})
    endif()
endforeach()
set({name}_LIBS{build_type_suffix} ${{{name}_LIBRARIES{build_type_suffix}}})
"""
