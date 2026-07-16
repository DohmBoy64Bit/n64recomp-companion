cmake_minimum_required(VERSION 3.24)
project({{PROJECT_IDENT}} VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(N64_STARTER_ENABLE_RT64 "Fetch and link RT64 renderer support" ON)
option(N64_STARTER_ENABLE_RMLUI "Link RmlUi for launcher and in-game menu assets" ON)
option(N64_STARTER_ENABLE_SVG "Enable LunaSVG dependency used by RmlUi SVG support" ON)
option(N64_STARTER_COPY_ASSETS "Copy runtime assets next to the executable" ON)

include(cmake/Dependencies.cmake)

add_executable(n64_runtime_starter
    src/main.cpp
    src/app_settings.hpp
    src/asset_paths.cpp
    src/asset_paths.hpp
    src/rt64_support.cpp
    src/rt64_support.hpp
    src/rmlui_manifest.cpp
    src/rmlui_manifest.hpp
)

target_compile_definitions(n64_runtime_starter PRIVATE
    N64_STARTER_PROJECT_NAME="{{PROJECT_NAME}}"
    N64_STARTER_WINDOW_TITLE="{{CPP_WINDOW_TITLE}}"
    N64_STARTER_ASSET_DIR="assets"
)

target_link_libraries(n64_runtime_starter PRIVATE SDL2::SDL2 SDL2::SDL2main)

if(N64_STARTER_ENABLE_RMLUI)
    target_compile_definitions(n64_runtime_starter PRIVATE N64_STARTER_HAS_RMLUI=1)
    target_link_libraries(n64_runtime_starter PRIVATE RmlUi::RmlUi Freetype::Freetype)
else()
    target_compile_definitions(n64_runtime_starter PRIVATE N64_STARTER_HAS_RMLUI=0)
endif()

if(N64_STARTER_ENABLE_SVG)
    target_compile_definitions(n64_runtime_starter PRIVATE N64_STARTER_HAS_LUNASVG=1)
    target_link_libraries(n64_runtime_starter PRIVATE lunasvg::lunasvg)
else()
    target_compile_definitions(n64_runtime_starter PRIVATE N64_STARTER_HAS_LUNASVG=0)
endif()

if(N64_STARTER_ENABLE_RT64)
    target_compile_definitions(n64_runtime_starter PRIVATE N64_STARTER_HAS_RT64=1)
    target_link_libraries(n64_runtime_starter PRIVATE rt64)
else()
    target_compile_definitions(n64_runtime_starter PRIVATE N64_STARTER_HAS_RT64=0)
endif()

if(MSVC)
    target_compile_options(n64_runtime_starter PRIVATE /W4 /permissive-)
else()
    target_compile_options(n64_runtime_starter PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(N64_STARTER_COPY_ASSETS)
    add_custom_command(TARGET n64_runtime_starter POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_directory
                "${CMAKE_CURRENT_SOURCE_DIR}/assets"
                "$<TARGET_FILE_DIR:n64_runtime_starter>/assets"
        VERBATIM)
endif()

install(TARGETS n64_runtime_starter RUNTIME DESTINATION .)
install(DIRECTORY assets DESTINATION .)
