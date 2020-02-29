cmake_minimum_required(VERSION 2.8.12)
project(PackageTest CXX)

find_package(hello)
add_library(bye bye.cpp)
target_link_libraries(bye hello::hello)
