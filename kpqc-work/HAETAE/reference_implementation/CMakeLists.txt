## SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.18)
project(
  haetae
  LANGUAGES C
  VERSION 1.0.0
  DESCRIPTION "HAETAE Reference Implementation")

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib/)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib/)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin/)
set(EXECUTABLE_OUTPUT_PATH ${CMAKE_BINARY_DIR}/bin/)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(srcs
    src/decompose.c
    src/encoding.c
    src/fft.c
    src/fixpoint.c
    src/ntt.c
    src/packing.c
    src/poly.c
    src/polyvec.c
    src/polymat.c
    src/polyfix.c
    src/reduce.c
    src/sampler.c
    src/sign.c)

add_library(haetae_include INTERFACE)
target_include_directories(haetae_include
                           INTERFACE ${PROJECT_SOURCE_DIR}/include)

add_library(haetae_rng OBJECT ${PROJECT_SOURCE_DIR}/src/randombytes.c)
target_link_libraries(haetae_rng PRIVATE haetae_include)
set_target_properties(haetae_rng PROPERTIES POSITION_INDEPENDENT_CODE ON)

add_library(haetae_fips202 OBJECT ${PROJECT_SOURCE_DIR}/src/fips202.c
                                  ${PROJECT_SOURCE_DIR}/src/symmetric-shake.c)
target_link_libraries(haetae_fips202 PRIVATE haetae_include)
set_target_properties(haetae_fips202 PROPERTIES POSITION_INDEPENDENT_CODE ON)

set(LIB_NAME2 ${PROJECT_NAME}-mode2)
add_library(${LIB_NAME2} SHARED ${srcs})
target_compile_definitions(${LIB_NAME2} PUBLIC HAETAE_CONFIG_MODE=HAETAE_MODE2)
target_link_libraries(${LIB_NAME2} PRIVATE haetae_rng haetae_fips202
                                           haetae_include)

set(LIB_NAME3 ${PROJECT_NAME}-mode3)
add_library(${LIB_NAME3} SHARED ${srcs})
target_compile_definitions(${LIB_NAME3} PUBLIC HAETAE_CONFIG_MODE=HAETAE_MODE3)
target_link_libraries(${LIB_NAME3} PRIVATE haetae_rng haetae_fips202
                                           haetae_include)

set(LIB_NAME5 ${PROJECT_NAME}-mode5)
add_library(${LIB_NAME5} SHARED ${srcs})
target_compile_definitions(${LIB_NAME5} PUBLIC HAETAE_CONFIG_MODE=HAETAE_MODE5)
target_link_libraries(${LIB_NAME5} PRIVATE haetae_rng haetae_fips202
                                           haetae_include)

option(HAETAE_BUILD_TEST "Build the test suite" ON)

if(${HAETAE_BUILD_TEST})
  add_subdirectory(test)
endif()

add_subdirectory(kat)
add_subdirectory(benchmark)
