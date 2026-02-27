import textwrap

lib_h = textwrap.dedent("""
    #pragma once
    #include <string>
    class HelloLib {
    public:
        void hello(const std::string& name);
    };
""")

lib_cpp = textwrap.dedent("""
    #include "hello.h"
    #include <iostream>
    using namespace std;
    void HelloLib::hello(const std::string& name) {
        #ifdef DEBUG
        std::cout << "Hello " << name << " Debug!" <<std::endl;
        #else
        std::cout << "Hello " << name << " Release!" <<std::endl;
        #endif
    }
""")

cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.1)
    project(MyHello CXX)
    set(SOURCES
      hello.cpp
   )
    set(HEADERS
        hello.h
    )
    add_library (hello ${SOURCES} ${HEADERS})
    set_target_properties(hello PROPERTIES PUBLIC_HEADER "${HEADERS}")
    install(TARGETS hello
        RUNTIME DESTINATION bin
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib
        PUBLIC_HEADER DESTINATION include
    )
""")


def create_library(client):
    client.save({
        'hello.h': lib_h,
        'hello.cpp': lib_cpp,
        'CMakeLists.txt': cmakelists
    })
