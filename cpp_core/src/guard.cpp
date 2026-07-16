// minxg_cpp_guard -- memory safety guard implementation.
//
// Every function here is noexcept and returns a simple valid/invalid
// result.  No exceptions, no allocations, no side effects.

#include "minxg_guard.hpp"
#include <cstring>
#include <cctype>

namespace minxg_guard {

bool validate_buffer(const void* ptr, std::size_t claimed_len) noexcept {
    if (ptr == nullptr) return false;
    if (claimed_len == 0) return true;  // empty buffer is valid
    // We cannot truly verify the buffer extent without OS help,
    // but we can catch the obvious cases.  A production build
    // would use mmap + mincore on Linux or VirtualQuery on Windows.
    return claimed_len <= (1ULL << 30);  // sanity: < 1 GiB
}

bool validate_cstring(const char* str) noexcept {
    if (str == nullptr) return false;
    if (str[0] == '\0') return false;  // empty string rejected
    // Check first 256 chars are printable ASCII (storage/emulated can
    // have non-UTF8 paths, but our contracts are ASCII)
    for (int i = 0; i < 256 && str[i] != '\0'; ++i) {
        unsigned char c = static_cast<unsigned char>(str[i]);
        if (c < 32 && c != '\t' && c != '\n' && c != '\r') return false;
    }
    return true;
}

BorrowedBuffer::BorrowedBuffer(const void* ptr, std::size_t len)
    : ptr_(ptr), len_(len), valid_(validate_buffer(ptr, len)) {}

bool check_index(std::size_t idx, std::size_t bound) noexcept {
    return idx < bound;
}

std::optional<std::size_t> safe_substr_len(
    std::size_t str_len, std::size_t start, std::size_t max_len) noexcept {
    if (start > str_len) return std::nullopt;
    std::size_t remaining = str_len - start;
    return (remaining < max_len) ? remaining : max_len;
}

} // namespace minxg_guard
