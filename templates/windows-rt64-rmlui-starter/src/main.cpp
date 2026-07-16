#include "app_settings.hpp"
#include "asset_paths.hpp"
#include "rt64_support.hpp"
#include "rmlui_manifest.hpp"

#include <SDL.h>

#include <iostream>
#include <string>

namespace {
void print_startup_summary() {
    std::cout << starter::project_name << '\n';
    std::cout << "RT64: " << starter::rt64_support::status() << '\n';
    std::cout << "RmlUi: " << (starter::rmlui_manifest::rmlui_enabled() ? "linked" : "disabled") << '\n';
    std::cout << "LunaSVG: " << (starter::rmlui_manifest::svg_enabled() ? "linked" : "disabled") << '\n';
    std::cout << "Assets: " << (starter::required_assets_present() ? "present" : "missing") << '\n';
}
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;

    print_startup_summary();

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) != 0) {
        std::cerr << "SDL_Init failed: " << SDL_GetError() << '\n';
        return 1;
    }

    SDL_Window *window = SDL_CreateWindow(
        starter::window_title,
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        starter::default_width,
        starter::default_height,
        SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE
    );

    if (window == nullptr) {
        std::cerr << "SDL_CreateWindow failed: " << SDL_GetError() << '\n';
        SDL_Quit();
        return 1;
    }

    std::string title = std::string(starter::window_title) + " - " + std::string(starter::rt64_support::status());
    SDL_SetWindowTitle(window, title.c_str());

    bool running = true;
    while (running) {
        SDL_Event event{};
        while (SDL_PollEvent(&event) != 0) {
            if (event.type == SDL_QUIT) {
                running = false;
            }
            if (event.type == SDL_KEYDOWN && event.key.keysym.sym == SDLK_ESCAPE) {
                running = false;
            }
        }
        SDL_Delay(16);
    }

    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
