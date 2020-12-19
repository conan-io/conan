#include <iostream>
#include "pkg.h"

void pkg(){
    #ifdef NDEBUG
    std::cout << "pkg/0.1: Hello World Release!" <<std::endl;
    #else
    std::cout << "pkg/0.1: Hello World Debug!" <<std::endl;
    #endif
}
