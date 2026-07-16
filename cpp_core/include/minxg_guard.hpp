// minxg_cpp_guard -- memory safety guard for MINXG native bridge.
//
// Design: every FFI input is NULL-checked, bounds-checked, and
// lifetime-validated before it touches Python or Rust.  This is
// the "security guard" layer -- C++'s job is to be correct, not
// fast (fast is Rust's job).
//
// License: MIT (same as project)

#pragma once
#include <cstddef>
#include <cstdint>
#include <string_view>
#include <optional>

namespace minxg_guard {

// Validate a raw pointer is non-null and within a claimed length.
// Returns true if safe, false if the call should be refused.
bool validate_buffer(const void* ptr, std::size_t claimed_len) noexcept;

// Validate a C string pointer (non-null, non-empty, printable ASCII).
bool validate_cstring(const char* str) noexcept;

// RAII wrapper for a borrowed buffer -- asserts validity on
// construction, releases on destruction.  No ownership transfer.
class BorrowedBuffer {
public:
    BorrowedBuffer(const void* ptr, std::size_t len);
    ~BorrowedBuffer() = default;
    BorrowedBuffer(const BorrowedBuffer&) = delete;
    BorrowedBuffer& operator=(const BorrowedBuffer&) = delete;

    bool valid() const noexcept { return valid_; }
    const void* data() const noexcept { return ptr_; }
    std::size_t size() const noexcept { return len_; }

private:
    const void* ptr_;
    std::size_t len_;
    bool valid_;
};

// Check that an index is within [0, bound).  Returns true if safe.
bool check_index(std::size_t idx, std::size_t bound) noexcept;

// Compute safe substring length to avoid OOB reads.
std::optional<std::size_t> safe_substr_len(
    std::size_t str_len, std::size_t start, std::size_t max_len) noexcept;

} // namespace minxg_guard
