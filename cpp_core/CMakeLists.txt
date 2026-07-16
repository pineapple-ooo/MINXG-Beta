cmake_minimum_required(VERSION 3.14)
project(minxg_cpp_guard LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Strict warnings = memory safety guard duty
if(MSVC)
    add_compile_options(/W4 /WX /permissive-)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -Werror -Wconversion)
endif()

add_library(minxg_guard STATIC src/guard.cpp)
target_include_DIRECTORIES(minxg_guard PUBLIC include)
