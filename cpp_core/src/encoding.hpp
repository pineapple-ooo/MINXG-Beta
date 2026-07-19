#ifndef MULTILING_ENCODING_HPP
#define MULTILING_ENCODING_HPP

#include <string>
#include <vector>
#include <cstdint>

namespace multiling {

/**
 * @brief Encoding conversion utilities for text processing
 */
class Encoding {
public:
    /**
     * @brief Convert UTF-8 string to UTF-16 (Windows-compatible)
     * @param input UTF-8 encoded string
     * @return UTF-16 encoded string as uint16_t vector
     */
    static std::vector<uint16_t> utf8ToUtf16(const std::string& input);

    /**
     * @brief Convert UTF-16 to UTF-8 string
     * @param input UTF-16 encoded data
     * @return UTF-8 encoded string
     */
    static std::string utf16ToUtf8(const std::vector<uint16_t>& input);

    /**
     * @brief Convert UTF-8 to Latin-1 (ISO-8859-1) encoding
     * @param input UTF-8 encoded string
     * @return Latin-1 encoded string (lossy for non-Latin chars)
     */
    static std::string utf8ToLatin1(const std::string& input);

    /**
     * @brief Calculate byte length of UTF-8 string
     * @param input UTF-8 string
     * @return Number of bytes
     */
    static size_t utf8ByteLength(const std::string& input);

    /**
     * @brief Count codepoints in UTF-8 string
     * @param input UTF-8 string
     * @return Number of Unicode codepoints
     */
    static size_t utf8CodepointCount(const std::string& input);

    /**
     * @brief Check if string is valid UTF-8
     * @param input String to validate
     * @return true if valid UTF-8
     */
    static bool isValidUtf8(const std::string& input);
};

} // namespace multiling

#endif // MULTILING_ENCODING_HPP