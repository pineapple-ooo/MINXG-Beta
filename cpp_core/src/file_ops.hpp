// file_ops.hpp — RAII file I/O, mmap, glob, stat, copy (C++17, no std::span)
#ifndef FILE_OPS_HPP
#define FILE_OPS_HPP

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace cpp_core::file_ops {

// ─── Byte Views (C++17 replacement for std::span) ────────────────────────────
struct ByteView {
    std::byte* ptr{nullptr};
    std::size_t len{0};
    ByteView() = default;
    ByteView(std::byte* p, std::size_t n) noexcept : ptr(p), len(n) {}
    bool empty() const noexcept { return len == 0; }
    std::byte* begin() noexcept { return ptr; }
    std::byte* end() noexcept { return ptr + len; }
};

struct ConstByteView {
    const std::byte* ptr{nullptr};
    std::size_t len{0};
    ConstByteView() = default;
    ConstByteView(const std::byte* p, std::size_t n) noexcept : ptr(p), len(n) {}
    ConstByteView(const ByteView& v) noexcept : ptr(v.ptr), len(v.len) {}
    bool empty() const noexcept { return len == 0; }
    const std::byte* begin() const noexcept { return ptr; }
    const std::byte* end() const noexcept { return ptr + len; }
};

// ─── MappedFile — RAII memory-mapped file ─────────────────────────────────────
class MappedFile {
public:
    MappedFile() = default;
    MappedFile(const std::string& path, bool read_only = true);
    ~MappedFile();

    MappedFile(MappedFile&& other) noexcept;
    MappedFile& operator=(MappedFile&& other) noexcept;
    MappedFile(const MappedFile&) = delete;
    MappedFile& operator=(const MappedFile&) = delete;

    bool is_open() const noexcept;
    explicit operator bool() const noexcept { return is_open(); }
    const std::string& path() const { return path_; }
    std::size_t size() const noexcept { return size_; }
    ConstByteView view() const noexcept { return {data_, size_}; }

    // data() returns nullptr if not open
    const std::byte* data() const noexcept { return data_; }

    static bool unmapped(const std::string& path);

private:
    void close() noexcept;
    std::string path_;
    std::byte* data_{nullptr};
    std::size_t size_{0};
    int fd_{-1};
};

// ─── FileReader — RAII sequential file reader ─────────────────────────────────
class FileReader {
public:
    FileReader() = default;
    explicit FileReader(const std::string& path);
    ~FileReader();

    FileReader(FileReader&& other) noexcept;
    FileReader& operator=(FileReader&& other) noexcept;
    FileReader(const FileReader&) = delete;
    FileReader& operator=(const FileReader&) = delete;

    bool is_open() const noexcept;
    explicit operator bool() const noexcept { return is_open(); }
    void close() noexcept;

    // Read up to buffer.len bytes; returns bytes read
    std::size_t read(ByteView buffer) noexcept;
    // Read exactly n bytes into buffer (reads until n or EOF)
    bool read_exact(ByteView buffer, std::size_t n) noexcept;
    // Read all remaining bytes
    std::vector<std::byte> read_all() noexcept;

private:
    void* handle_{nullptr};  // FILE*
    std::string path_;
};

// ─── FileWriter — RAII sequential file writer ────────────────────────────────
class FileWriter {
public:
    enum Mode { Truncate, Append };
    FileWriter() = default;
    explicit FileWriter(const std::string& path, Mode mode = Truncate);
    ~FileWriter();

    FileWriter(FileWriter&& other) noexcept;
    FileWriter& operator=(FileWriter&& other) noexcept;
    FileWriter(const FileWriter&) = delete;
    FileWriter& operator=(const FileWriter&) = delete;

    bool is_open() const noexcept;
    explicit operator bool() const noexcept { return is_open(); }
    void close() noexcept;
    bool flush() noexcept;

    // Write buffer contents; returns bytes written
    std::size_t write(ConstByteView data) noexcept;
    // Write string
    std::size_t write(const std::string& s) noexcept;

private:
    void* handle_{nullptr};  // FILE*
    std::string path_;
};

// ─── High-level helpers ───────────────────────────────────────────────────────
std::vector<std::string> glob(const std::string& pattern);
bool exists(const std::string& path);
bool is_file(const std::string& path);
bool is_dir(const std::string& path);
std::optional<std::uintmax_t> file_size(const std::string& path);
bool copy_file(const std::string& src, const std::string& dst, bool overwrite = false);
bool remove_file(const std::string& path);
bool create_dir(const std::string& path);
bool remove_dir(const std::string& path);
std::string read_text(const std::string& path);
bool write_text(const std::string& path, const std::string& content);

}  // namespace cpp_core::file_ops

#endif  // FILE_OPS_HPP