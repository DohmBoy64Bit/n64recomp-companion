#include "rmlui_manifest.hpp"

#include <array>

namespace starter::rmlui_manifest {
namespace {
constexpr std::array<std::string_view, 5> kFiles = {
    "ui/launcher.rml",
    "ui/pause_menu.rml",
    "ui/settings.rml",
    "ui/styles/main.rcss",
    "ui/svg/logo.svg",
};
}

std::span<const std::string_view> files() {
    return kFiles;
}

bool rmlui_enabled() {
#if N64_STARTER_HAS_RMLUI
    return true;
#else
    return false;
#endif
}

bool svg_enabled() {
#if N64_STARTER_HAS_LUNASVG
    return true;
#else
    return false;
#endif
}
}
