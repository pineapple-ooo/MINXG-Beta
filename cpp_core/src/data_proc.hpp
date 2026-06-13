#ifndef MULTILING_DATA_PROC_HPP
#define MULTILING_DATA_PROC_HPP

#include <string>
#include <vector>
#include <map>

namespace multiling {

/**
 * @brief Data processing utilities for text analysis and transformation
 */
class DataProc {
public:
    /**
     * @brief Tokenize string by delimiters
     * @param input Input string
     * @param delimiters Delimiter characters
     * @return Vector of tokens
     */
    static std::vector<std::string> tokenize(const std::string& input, const std::string& delimiters = " \t\n");

    /**
     * @brief Remove leading and trailing whitespace
     * @param input Input string
     * @return Trimmed string
     */
    static std::string trim(const std::string& input);

    /**
     * @brief Convert string to lowercase
     * @param input Input string
     * @return Lowercased string
     */
    static std::string toLower(const std::string& input);

    /**
     * @brief Convert string to uppercase
     * @param input Input string
     * @return Uppercased string
     */
    static std::string toUpper(const std::string& input);

    /**
     * @brief Calculate word frequency from text
     * @param input Input text
     * @return Map of word to frequency
     */
    static std::map<std::string, size_t> wordFrequency(const std::string& input);

    /**
     * @brief Pad string to specified length
     * @param input Input string
     * @param length Target length
     * @param padChar Padding character
     * @param padRight Pad on right side (true) or left (false)
     * @return Padded string
     */
    static std::string pad(const std::string& input, size_t length, char padChar = ' ', bool padRight = true);

    /**
     * @brief Truncate string to specified length
     * @param input Input string
     * @param length Maximum length
     * @param suffix Suffix to append if truncated
     * @return Truncated string
     */
    static std::string truncate(const std::string& input, size_t length, const std::string& suffix = "...");

    /**
     * @brief Split string into lines
     * @param input Input string
     * @return Vector of lines
     */
    static std::vector<std::string> splitLines(const std::string& input);

    /**
     * @brief Join strings with separator
     * @param strings Vector of strings
     * @param separator Separator to use
     * @return Joined string
     */
    static std::string join(const std::vector<std::string>& strings, const std::string& separator);
};

} // namespace multiling

#endif // MULTILING_DATA_PROC_HPP