#include "encoding.hpp"
#include <stdexcept>
#include <algorithm>

namespace multiling {

std::vector<uint16_t> Encoding::utf8ToUtf16(const std::string& input) {
    std::vector<uint16_t> result;
    result.reserve(input.size() / 2);

    size_t i = 0;
    while (i < input.size()) {
        uint32_t codepoint = 0;
        uint8_t byte = static_cast<uint8_t>(input[i]);

        if ((byte & 0x80) == 0) {
            codepoint = byte;
            i += 1;
        } else if ((byte & 0xE0) == 0xC0) {
            if (i + 1 >= input.size()) break;
            codepoint = (byte & 0x1F) << 6;
            codepoint |= (static_cast<uint8_t>(input[i + 1]) & 0x3F);
            i += 2;
        } else if ((byte & 0xF0) == 0xE0) {
            if (i + 2 >= input.size()) break;
            codepoint = (byte & 0x0F) << 12;
            codepoint |= (static_cast<uint8_t>(input[i + 1]) & 0x3F) << 6;
            codepoint |= (static_cast<uint8_t>(input[i + 2]) & 0x3F);
            i += 3;
        } else if ((byte & 0xF8) == 0xF0) {
            if (i + 3 >= input.size()) break;
            codepoint = (byte & 0x07) << 18;
            codepoint |= (static_cast<uint8_t>(input[i + 1]) & 0x3F) << 12;
            codepoint |= (static_cast<uint8_t>(input[i + 2]) & 0x3F) << 6;
            codepoint |= (static_cast<uint8_t>(input[i + 3]) & 0x3F);
            i += 4;
        } else {
            i += 1;
            continue;
        }

        if (codepoint <= 0xFFFF) {
            result.push_back(static_cast<uint16_t>(codepoint));
        } else {
            codepoint -= 0x10000;
            result.push_back(static_cast<uint16_t>(0xD800 | (codepoint >> 10)));
            result.push_back(static_cast<uint16_t>(0xDC00 | (codepoint & 0x3FF)));
        }
    }
    return result;
}

std::string Encoding::utf16ToUtf8(const std::vector<uint16_t>& input) {
    std::string result;
    result.reserve(input.size() * 3 / 2);

    for (size_t i = 0; i < input.size(); ++i) {
        uint32_t codepoint = input[i];

        if (codepoint >= 0xD800 && codepoint <= 0xDBFF && i + 1 < input.size()) {
            uint16_t low = input[i + 1];
            if (low >= 0xDC00 && low <= 0xDFFF) {
                codepoint = 0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00);
                ++i;
            }
        }

        if (codepoint <= 0x7F) {
            result.push_back(static_cast<char>(codepoint));
        } else if (codepoint <= 0x7FF) {
            result.push_back(static_cast<char>(0xC0 | (codepoint >> 6)));
            result.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
        } else if (codepoint <= 0xFFFF) {
            result.push_back(static_cast<char>(0xE0 | (codepoint >> 12)));
            result.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
            result.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
        } else {
            result.push_back(static_cast<char>(0xF0 | (codepoint >> 18)));
            result.push_back(static_cast<char>(0x80 | ((codepoint >> 12) & 0x3F)));
            result.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
            result.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
        }
    }
    return result;
}

std::string Encoding::utf8ToLatin1(const std::string& input) {
    std::string result;
    result.reserve(input.size());

    size_t i = 0;
    while (i < input.size()) {
        uint8_t byte = static_cast<uint8_t>(input[i]);

        if ((byte & 0x80) == 0) {
            result.push_back(static_cast<char>(byte));
            ++i;
        } else {
            uint32_t codepoint = 0;
            size_t len = 0;

            if ((byte & 0xE0) == 0xC0) {
                codepoint = byte & 0x1F;
                len = 2;
            } else if ((byte & 0xF0) == 0xE0) {
                codepoint = byte & 0x0F;
                len = 3;
            } else if ((byte & 0xF8) == 0xF0) {
                codepoint = byte & 0x07;
                len = 4;
            }

            for (size_t j = 1; j < len && i + j < input.size(); ++j) {
                codepoint = (codepoint << 6) | (static_cast<uint8_t>(input[i + j]) & 0x3F);
            }

            result.push_back(codepoint <= 0xFF ? static_cast<char>(codepoint) : '?');
            i += len > 0 ? len : 1;
        }
    }
    return result;
}

size_t Encoding::utf8ByteLength(const std::string& input) {
    return input.size();
}

size_t Encoding::utf8CodepointCount(const std::string& input) {
    size_t count = 0;
    size_t i = 0;
    while (i < input.size()) {
        uint8_t byte = static_cast<uint8_t>(input[i]);
        if ((byte & 0x80) == 0) {
            i += 1;
        } else if ((byte & 0xE0) == 0xC0) {
            i += 2;
        } else if ((byte & 0xF0) == 0xE0) {
            i += 3;
        } else if ((byte & 0xF8) == 0xF0) {
            i += 4;
        } else {
            i += 1;
        }
        ++count;
    }
    return count;
}

bool Encoding::isValidUtf8(const std::string& input) {
    size_t i = 0;
    while (i < input.size()) {
        uint8_t byte = static_cast<uint8_t>(input[i]);

        if ((byte & 0x80) == 0) {
            i += 1;
        } else if ((byte & 0xE0) == 0xC0) {
            if (i + 1 >= input.size() || (input[i + 1] & 0xC0) != 0x80) return false;
            i += 2;
        } else if ((byte & 0xF0) == 0xE0) {
            if (i + 2 >= input.size()) return false;
            if ((input[i + 1] & 0xC0) != 0x80) return false;
            if ((input[i + 2] & 0xC0) != 0x80) return false;
            i += 3;
        } else if ((byte & 0xF8) == 0xF0) {
            if (i + 3 >= input.size()) return false;
            if ((input[i + 1] & 0xC0) != 0x80) return false;
            if ((input[i + 2] & 0xC0) != 0x80) return false;
            if ((input[i + 3] & 0xC0) != 0x80) return false;
            i += 4;
        } else {
            return false;
        }
    }
    return true;
}

} // namespace multiling