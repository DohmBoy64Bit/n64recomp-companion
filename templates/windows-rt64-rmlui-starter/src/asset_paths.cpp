#include "asset_paths.hpp"

#include <array>
#include <cstdlib>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

namespace starter {
std::filesystem::path executable_directory() {
#if defined(_WIN32)
    std::array<wchar_t, 32768> buffer{};
    const DWORD count = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (count > 0 && count < buffer.size()) {
        return std::filesystem::path(buffer.data()).parent_path();
    }
#endif
    return std::filesystem::current_path();
}

std::filesystem::path asset_directory() {
    return executable_directory() / N64_STARTER_ASSET_DIR;
}

bool required_assets_present() {
    const auto root = asset_directory();
    return std::filesystem::exists(root / "ui" / "launcher.rml") &&
           std::filesystem::exists(root / "ui" / "pause_menu.rml") &&
           std::filesystem::exists(root / "ui" / "settings.rml") &&
           std::filesystem::exists(root / "ui" / "styles" / "main.rcss") &&
           std::filesystem::exists(root / "ui" / "svg" / "logo.svg");
}
}
