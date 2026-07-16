#pragma once

#include <filesystem>

namespace starter {
std::filesystem::path executable_directory();
std::filesystem::path asset_directory();
bool required_assets_present();
}
