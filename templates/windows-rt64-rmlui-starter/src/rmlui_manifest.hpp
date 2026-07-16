#pragma once

#include <span>
#include <string_view>

namespace starter::rmlui_manifest {
std::span<const std::string_view> files();
bool rmlui_enabled();
bool svg_enabled();
}
