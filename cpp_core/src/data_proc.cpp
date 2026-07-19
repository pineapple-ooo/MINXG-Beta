#include "data_proc.hpp"
#include <algorithm>
#include <cctype>
#include <sstream>

namespace multiling {

std::vector<std::string> DataProc::tokenize(const std::string& input, const std::string& delimiters) {
    std::vector<std::string> tokens;
    std::string::size_type start = 0;
    std::string::size_type end = input.find_first_of(delimiters);

    while (end != std::string::npos) {
        if (end > start) {
            tokens.emplace_back(input.substr(start, end - start));
        }
        start = end + 1;
        end = input.find_first_of(delimiters, start);
    }

    if (start < input.size()) {
        tokens.emplace_back(input.substr(start));
    }

    return tokens;
}

std::string DataProc::trim(const std::string& input) {
    if (input.empty()) return input;

    size_t start = 0;
    size_t end = input.size() - 1;

    while (start < input.size() && std::isspace(static_cast<unsigned char>(input[start]))) {
        ++start;
    }

    while (end > start && std::isspace(static_cast<unsigned char>(input[end]))) {
        --end;
    }

    return input.substr(start, end - start + 1);
}

std::string DataProc::toLower(const std::string& input) {
    std::string result = input;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    return result;
}

std::string DataProc::toUpper(const std::string& input) {
    std::string result = input;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c) { return std::toupper(c); });
    return result;
}

std::map<std::string, size_t> DataProc::wordFrequency(const std::string& input) {
    std::map<std::string, size_t> freq;
    auto tokens = tokenize(input);

    for (const auto& word : tokens) {
        std::string lower = toLower(trim(word));
        if (!lower.empty()) {
            ++freq[lower];
        }
    }

    return freq;
}

std::string DataProc::pad(const std::string& input, size_t length, char padChar, bool padRight) {
    if (input.size() >= length) {
        return input;
    }

    std::string result(input);
    size_t padding = length - input.size();

    if (padRight) {
        result.append(padding, padChar);
    } else {
        result.insert(0, padding, padChar);
    }

    return result;
}

std::string DataProc::truncate(const std::string& input, size_t length, const std::string& suffix) {
    if (input.size() <= length) {
        return input;
    }

    if (length < suffix.size()) {
        return input.substr(0, length);
    }

    return input.substr(0, length - suffix.size()) + suffix;
}

std::vector<std::string> DataProc::splitLines(const std::string& input) {
    std::vector<std::string> lines;
    std::istringstream stream(input);
    std::string line;

    while (std::getline(stream, line)) {
        // Remove trailing carriage return for Windows line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        lines.push_back(line);
    }

    // Handle case where input doesn't end with newline
    if (input.empty() || input.back() == '\n' || input.back() == '\r') {
        // Already handled by getline behavior
    }

    return lines;
}

std::string DataProc::join(const std::vector<std::string>& strings, const std::string& separator) {
    if (strings.empty()) return "";

    std::string result = strings[0];
    for (size_t i = 1; i < strings.size(); ++i) {
        result += separator + strings[i];
    }
    return result;
}

} // namespace multiling