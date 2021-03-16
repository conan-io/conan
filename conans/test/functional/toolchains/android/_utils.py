import textwrap

lib_h = textwrap.dedent("""
    int some_function(int value);
""")

lib_cpp = textwrap.dedent("""
    #include "lib.h"
    #include <iostream>

    int some_function(int value) {
        std::cout << "some_function(value=" << value << ")" << std::endl;
        return 42;
    }
""")

cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 2.8.12)  # TODO: Define minimun required here
    project(AndroidLibrary CXX)

    add_library(library lib.h lib.cpp)
    set_target_properties(library PROPERTIES PUBLIC_HEADER lib.h)

    install(TARGETS library
        RUNTIME DESTINATION bin
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib
        PUBLIC_HEADER DESTINATION include
    )
""")


def create_library(client):
    client.save({
        'lib.h': lib_h,
        'lib.cpp': lib_cpp,
        'CMakeLists.txt': cmakelists
    })
