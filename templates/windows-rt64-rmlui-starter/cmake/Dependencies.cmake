include(FetchContent)

set(FETCHCONTENT_QUIET OFF)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Use static libraries for starter dependencies" FORCE)

find_package(SDL2 CONFIG REQUIRED)

if(N64_STARTER_ENABLE_RMLUI)
    set(RMLUI_SAMPLES OFF CACHE BOOL "Disable RmlUi samples" FORCE)
    set(RMLUI_LUA_BINDINGS OFF CACHE BOOL "Disable RmlUi Lua bindings" FORCE)
    set(RMLUI_SVG_PLUGIN ${N64_STARTER_ENABLE_SVG} CACHE BOOL "Enable RmlUi SVG plugin" FORCE)
    set(RMLUI_FONT_ENGINE freetype CACHE STRING "Use FreeType font engine" FORCE)
    find_package(Freetype REQUIRED)
    find_package(RmlUi CONFIG REQUIRED)
endif()

if(N64_STARTER_ENABLE_SVG)
    find_package(lunasvg CONFIG REQUIRED)
endif()

if(N64_STARTER_ENABLE_RT64)
    set(RT64_STATIC ON CACHE BOOL "Build RT64 as a static library" FORCE)
    FetchContent_Declare(
        rt64
        GIT_REPOSITORY https://github.com/rt64/rt64.git
        GIT_TAG main
        GIT_SHALLOW TRUE
        GIT_PROGRESS TRUE
    )
    FetchContent_MakeAvailable(rt64)
    if(NOT TARGET rt64)
        message(FATAL_ERROR "RT64 was fetched, but the expected CMake target 'rt64' was not created")
    endif()
endif()
