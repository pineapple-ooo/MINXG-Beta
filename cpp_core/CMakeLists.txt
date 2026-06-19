cmake_minimum_required(VERSION 3.10)
project(cpp_core VERSION 1.0.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)

find_package(OpenSSL REQUIRED)

# C wrapper — pure C, no C++. Links text_engine.c (slugs/word_freq)
# so undefined-sym crashes don't happen on dlopen.
add_library(minxg_core SHARED
    cpp_wrapper.c
    ../c_core/text_engine.c
    ../c_core/text_engine.h
)
target_link_libraries(minxg_core PUBLIC OpenSSL::SSL OpenSSL::Crypto)
target_compile_options(minxg_core PRIVATE -fPIC -O3)
target_include_directories(minxg_core PRIVATE ../c_core)

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

# C++ JSON facade — flat C ABI for ctypes binding.
# Re-parses on every call (no C++ objects cross the ABI), returns
# malloc'd std::string buffers via cpp_json_free(); see header comment in
# json_stringify.cpp for the rationale.
add_library(minxg_cpp_json SHARED
    src/json_stringify.cpp
    src/json_fast.cpp
)
target_include_directories(minxg_cpp_json PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_compile_options(minxg_cpp_json PRIVATE -fPIC -O3 -std=c++17)