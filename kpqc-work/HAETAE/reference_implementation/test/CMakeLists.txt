## SPDX-License-Identifier: MIT

add_executable(${LIB_NAME2}-main main.c)
target_link_libraries(${LIB_NAME2}-main PRIVATE ${LIB_NAME2} haetae_include
                                                haetae_rng)

add_executable(${LIB_NAME3}-main main.c)
target_link_libraries(${LIB_NAME3}-main PRIVATE ${LIB_NAME3} haetae_include
                                                haetae_rng)

add_executable(${LIB_NAME5}-main main.c)
target_link_libraries(${LIB_NAME5}-main PRIVATE ${LIB_NAME5} haetae_include
                                                haetae_rng)
