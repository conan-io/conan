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
