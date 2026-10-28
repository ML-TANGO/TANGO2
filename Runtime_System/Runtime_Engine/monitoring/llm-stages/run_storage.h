// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <cstdint>
#include <filesystem>

namespace tango2
{
inline uintmax_t runDirectoryBytes(std::filesystem::path const& root)
{
    uintmax_t total = 0;
    auto const acknowledgements = root/"acknowledged";
    for (auto const& entry : std::filesystem::recursive_directory_iterator(root))
    {
        if (entry.path().parent_path() == acknowledgements && entry.path().extension() == ".tmp")
        {
            continue;
        }
        if (entry.is_regular_file()) { total += entry.file_size(); }
    }
    return total;
}
} // namespace tango2
