## SPDX-License-Identifier: MIT

set(kat_srcs kat_sign.c PQCgenKAT_sign.c rng.c)

find_package(OpenSSL REQUIRED)

add_executable(${LIB_NAME2}-kat ${kat_srcs})
target_link_libraries(${LIB_NAME2}-kat PRIVATE ${LIB_NAME2} haetae_include
                                               OpenSSL::Crypto)

add_executable(${LIB_NAME3}-kat ${kat_srcs})
target_link_libraries(${LIB_NAME3}-kat PRIVATE ${LIB_NAME3} haetae_include
                                               OpenSSL::Crypto)

add_executable(${LIB_NAME5}-kat ${kat_srcs})
target_link_libraries(${LIB_NAME5}-kat PRIVATE ${LIB_NAME5} haetae_include
                                               OpenSSL::Crypto)
