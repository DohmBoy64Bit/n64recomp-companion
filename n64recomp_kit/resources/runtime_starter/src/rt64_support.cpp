#include "rt64_support.hpp"

namespace starter::rt64_support {
bool linked() {
#if N64_STARTER_HAS_RT64
    return true;
#else
    return false;
#endif
}

std::string_view status() {
#if N64_STARTER_HAS_RT64
    return "RT64 CMake target linked";
#else
    return "RT64 disabled for this build";
#endif
}
}
