// compress.hpp — Zlib/Deflate/LZ4 fast compression wrappers (C++17)
// Used by the IPC layer between Python ↔ C++ ↔ Go to minimize socket overhead.

#ifndef MINXG_COMPRESS_HPP
#define MINXG_COMPRESS_HPP

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace cpp_core::compress {

enum class Algorithm {
    Deflate,   // zlib wrapper (RFC 1950)
    Gzip,      // gzip format (RFC 1952)
    RawDeflate // raw DEFLATE (RFC 1951)
};

struct CompressConfig {
    Algorithm algorithm = Algorithm::Deflate;
    int level = 6; // 0-9
    size_t dict_size = 16384; // sliding window
};

/*
 * Compress data. Returns empty optional on failure.
 */
std::optional<std::vector<std::byte>> compress(
    const std::byte* data, size_t len,
    const CompressConfig& config = {});

std::optional<std::vector<std::byte>> compress(
    const std::string& data,
    const CompressConfig& config = {});

/*
 * Decompress data. Returns empty optional on failure / corruption.
 * max_output prevents decompression bombs.
 */
std::optional<std::vector<std::byte>> decompress(
    const std::byte* data, size_t len,
    size_t max_output = 256 * 1024 * 1024 /* 256MB */);

std::optional<std::string> decompress_to_string(
    const std::byte* data, size_t len,
    size_t max_output = 256 * 1024 * 1024);

/*
 * Estimate compression ratio on first N bytes.
 */
double estimate_ratio(const std::byte* data, size_t len, size_t sample_size = 4096);

/*
 * Streaming deflate: push bytes incrementally, get compressed chunks.
 */
class DeflateStream {
public:
    explicit DeflateStream(int level = 6);
    ~DeflateStream();

    DeflateStream(DeflateStream&&) noexcept;
    DeflateStream& operator=(DeflateStream&&) noexcept;
    DeflateStream(const DeflateStream&) = delete;
    DeflateStream& operator=(const DeflateStream&) = delete;

    // Push input data; returns compressed output available so far.
    std::vector<std::byte> push(const std::byte* data, size_t len);
    std::vector<std::byte> push(const std::string& data);

    // Flush remaining and finalize stream.
    std::vector<std::byte> finish();

    size_t bytes_in() const;
    size_t bytes_out() const;

private:
    void* stream_{nullptr}; // z_stream*
    size_t bytes_in_{0};
    size_t bytes_out_{0};
    int level_;
};

/*
 * Streaming inflate: push compressed bytes, get decompressed chunks.
 */
class InflateStream {
public:
    InflateStream();
    ~InflateStream();

    InflateStream(InflateStream&&) noexcept;
    InflateStream& operator=(InflateStream&&) noexcept;
    InflateStream(const InflateStream&) = delete;
    InflateStream& operator=(const InflateStream&) = delete;

    std::vector<std::byte> push(const std::byte* data, size_t len);
    std::vector<std::byte> push(const std::string& data);
    std::vector<std::byte> finish();

    size_t bytes_in() const;
    size_t bytes_out() const;

private:
    void* stream_{nullptr};
    size_t bytes_in_{0};
    size_t bytes_out_{0};
};

} // namespace cpp_core::compress

#endif // MINXG_COMPRESS_HPP