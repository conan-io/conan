import unittest

from nose.plugins.attrib import attr


from conans.test.utils.tools import TestClient

hello_cpp = """#include <iostream>
#include "hello.h"

void hello(){
    #ifdef NDEBUG
    std::cout << "Hello World Release!" <<std::endl;
    #else
    std::cout << "Hello World Debug!" <<std::endl;
    #endif
}"""

hello_h = """
#pragma once

#ifdef WIN32
  #define HELLO_EXPORT __declspec(dllexport)
#else
  #define HELLO_EXPORT
#endif

HELLO_EXPORT void hello();
"""

bye_cpp = """
#include <iostream>
#include "bye.h"
#include "hello.h"

void bye(){

    hello();

    #ifdef NDEBUG
    std::cout << "bye World Release!" <<std::endl;
    #else
    std::cout << "bye World Debug!" <<std::endl;
    #endif

}
"""

bye_h = """
#pragma once

#ifdef WIN32
  #define HELLO_EXPORT __declspec(dllexport)
#else
  #define HELLO_EXPORT
#endif

HELLO_EXPORT void bye();

"""


def get_hello_files():

    cmakelists = generic_export_cmakelist % ("hello", "hello.cpp", "hello.h")
    return {"hello.cpp": hello_cpp, "hello.h": hello_h, "CMakeLists.txt": cmakelists}


@attr('slow')
class CMakeFindPathMultiGeneratorTest(unittest.TestCase):

    def test_native_export_multi(self):
