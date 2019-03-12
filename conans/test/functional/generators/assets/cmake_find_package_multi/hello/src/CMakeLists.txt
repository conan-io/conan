cmake_minimum_required(VERSION 2.8.12)
project(PackageTest CXX)

if(CONAN_LINK_RUNTIME)
    foreach(flag CMAKE_C_FLAGS_RELEASE CMAKE_CXX_FLAGS_RELEASE
                 CMAKE_C_FLAGS_RELWITHDEBINFO CMAKE_CXX_FLAGS_RELWITHDEBINFO
                 CMAKE_C_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_MINSIZEREL)
        if(DEFINED ${flag})
            string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} ${flag} "${${flag}}")
        endif()
    endforeach()
    foreach(flag CMAKE_C_FLAGS_DEBUG CMAKE_CXX_FLAGS_DEBUG)
        if(DEFINED ${flag})
            string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} ${flag} "${${flag}}")
        endif()
    endforeach()
endif()

add_library(hello hello.cpp)
