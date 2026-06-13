cmake_minimum_required(VERSION 3.10)
project(cpp_core VERSION 1.0.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)

find_package(OpenSSL REQUIRED)

# C wrapper — pure C, no C++, linked as shared library for ctypes
add_library(minxg_core SHARED cpp_wrapper.c)
target_link_libraries(minxg_core PUBLIC OpenSSL::SSL OpenSSL::Crypto)
target_compile_options(minxg_core PRIVATE -fPIC -O3)

# C++ core library — static lib for direct linking
enable_language(CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CORE_SOURCES
    src/base.cpp
    src/file_ops.cpp
    src/crypto.cpp
    src/encoding.cpp
    src/data_proc.cpp
)

add_library(core STATIC ${CORE_SOURCES})
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(core PUBLIC OpenSSL::SSL OpenSSL::Crypto)