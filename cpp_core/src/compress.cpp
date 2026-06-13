// compress.cpp — zlib-based compression with RAII streaming wrappers
#include "compress.hpp"
#include <zlib.h>
#include <cstring>
#include <algorithm>

namespace cpp_core::compress {

// ─── One-shot compress/decompress ────────────────────────────────────────────

static int zlib_window_bits(Algorithm algo) {
    switch (algo) {
    case Algorithm::Gzip:      return 15 + 16; // MAX_WBITS | GZIP_ENCODING
    case Algorithm::RawDeflate: return -15;     // -MAX_WBITS (raw)
    default:                   return 15;       // MAX_WBITS (zlib)
    }
}

std::optional<std::vector<std::byte>> compress(
    const std::byte* data, size_t len, const CompressConfig& config) {
    if (!data || len == 0) return std::vector<std::byte>{};

    z_stream zs{};
    int wbits = zlib_window_bits(config.algorithm);
    int rc = deflateInit2(&zs, config.level, Z_DEFLATED, wbits, 8,
                          Z_DEFAULT_STRATEGY);
    if (rc != Z_OK) return std::nullopt;

    size_t bound = deflateBound(&zs, static_cast<uLong>(len));
    std::vector<std::byte> out(bound);

    zs.next_in   = reinterpret_cast<Bytef*>(const_cast<std::byte*>(data));
    zs.avail_in  = static_cast<uInt>(len);
    zs.next_out  = reinterpret_cast<Bytef*>(out.data());
    zs.avail_out = static_cast<uInt>(out.size());

    rc = ::deflate(&zs, Z_FINISH);
    if (rc != Z_STREAM_END) { deflateEnd(&zs); return std::nullopt; }

    out.resize(zs.total_out);
    deflateEnd(&zs);
    return out;
}

std::optional<std::vector<std::byte>> compress(
    const std::string& data, const CompressConfig& config) {
    return compress(reinterpret_cast<const std::byte*>(data.data()),
                    data.size(), config);
}

std::optional<std::vector<std::byte>> decompress(
    const std::byte* data, size_t len, size_t max_output) {
    if (!data || len == 0) return std::vector<std::byte>{};

    z_stream zs{};
    int rc = inflateInit2(&zs, 15 + 32); // auto-detect zlib/gzip
    if (rc != Z_OK) return std::nullopt;

    std::vector<std::byte> out;
    const size_t chunk = 65536;

    zs.next_in  = reinterpret_cast<Bytef*>(const_cast<std::byte*>(data));
    zs.avail_in = static_cast<uInt>(len);

    do {
        size_t old_size = out.size();
        size_t new_size = std::min(old_size + chunk, max_output);
        if (new_size <= old_size) { inflateEnd(&zs); return std::nullopt; }
        out.resize(new_size);

        zs.next_out  = reinterpret_cast<Bytef*>(out.data()) + old_size;
        zs.avail_out = static_cast<uInt>(new_size - old_size);

        rc = ::inflate(&zs, Z_NO_FLUSH);
        if (rc == Z_STREAM_END) break;
        if (rc != Z_OK && rc != Z_BUF_ERROR) { inflateEnd(&zs); return std::nullopt; }

        // if avail_out > 0, we have space AND didn't finish — should not happen
    } while (rc != Z_STREAM_END);

    out.resize(zs.total_out);
    inflateEnd(&zs);
    return out;
}

std::optional<std::string> decompress_to_string(
    const std::byte* data, size_t len, size_t max_output) {
    auto bytes = decompress(data, len, max_output);
    if (!bytes) return std::nullopt;
    return std::string(reinterpret_cast<const char*>(bytes->data()), bytes->size());
}

double estimate_ratio(const std::byte* data, size_t len, size_t sample_size) {
    if (!data || len == 0) return 1.0;
    size_t sample = std::min(len, sample_size);
    auto result = compress(data, sample, {Algorithm::Deflate, 1});
    if (!result || result->empty()) return 1.0;
    return static_cast<double>(result->size()) / static_cast<double>(sample);
}

// ─── DeflateStream ──────────────────────────────────────────────────────────

DeflateStream::DeflateStream(int level) : level_(level) {
    z_stream* zs = new z_stream{};
    deflateInit2(zs, level, Z_DEFLATED, 15, 8, Z_DEFAULT_STRATEGY);
    stream_ = zs;
}

DeflateStream::~DeflateStream() {
    if (stream_) {
        auto* zs = static_cast<z_stream*>(stream_);
        deflateEnd(zs);
        delete zs;
    }
}

DeflateStream::DeflateStream(DeflateStream&& o) noexcept
    : stream_(o.stream_), bytes_in_(o.bytes_in_), bytes_out_(o.bytes_out_),
      level_(o.level_) {
    o.stream_ = nullptr;
}

DeflateStream& DeflateStream::operator=(DeflateStream&& o) noexcept {
    if (this != &o) {
        if (stream_) { auto* zs = static_cast<z_stream*>(stream_); deflateEnd(zs); delete zs; }
        stream_ = o.stream_; o.stream_ = nullptr;
        bytes_in_ = o.bytes_in_; bytes_out_ = o.bytes_out_;
    }
    return *this;
}

std::vector<std::byte> DeflateStream::push(const std::byte* data, size_t len) {
    if (!stream_ || !data || len == 0) return {};
    auto* zs = static_cast<z_stream*>(stream_);
    zs->next_in   = reinterpret_cast<Bytef*>(const_cast<std::byte*>(data));
    zs->avail_in  = static_cast<uInt>(len);
    bytes_in_ += len;

    std::vector<std::byte> out;
    const size_t chunk = 65536;

    do {
        size_t old_sz = out.size();
        out.resize(old_sz + chunk);
        zs->next_out  = reinterpret_cast<Bytef*>(out.data()) + old_sz;
        zs->avail_out = static_cast<uInt>(chunk);

        int rc = ::deflate(zs, Z_NO_FLUSH);
        size_t written = chunk - zs->avail_out;
        bytes_out_ += written;
        out.resize(old_sz + written);
        if (rc == Z_STREAM_ERROR) return {};
        if (zs->avail_out > 0) break;
    } while (true);

    return out;
}

std::vector<std::byte> DeflateStream::push(const std::string& data) {
    return push(reinterpret_cast<const std::byte*>(data.data()), data.size());
}

std::vector<std::byte> DeflateStream::finish() {
    if (!stream_) return {};
    auto* zs = static_cast<z_stream*>(stream_);

    zs->next_in  = nullptr;
    zs->avail_in = 0;

    std::vector<std::byte> out;
    const size_t chunk = 65536;

    do {
        size_t old_sz = out.size();
        out.resize(old_sz + chunk);
        zs->next_out  = reinterpret_cast<Bytef*>(out.data()) + old_sz;
        zs->avail_out = static_cast<uInt>(chunk);

        int rc = ::deflate(zs, Z_FINISH);
        size_t written = chunk - zs->avail_out;
        bytes_out_ += written;
        out.resize(old_sz + written);
        if (rc == Z_STREAM_END) break;
        if (rc != Z_OK) return {};
    } while (true);

    return out;
}

size_t DeflateStream::bytes_in() const { return bytes_in_; }
size_t DeflateStream::bytes_out() const { return bytes_out_; }

// ─── InflateStream ──────────────────────────────────────────────────────────

InflateStream::InflateStream() {
    z_stream* zs = new z_stream{};
    inflateInit2(zs, 15 + 32);
    stream_ = zs;
}

InflateStream::~InflateStream() {
    if (stream_) {
        auto* zs = static_cast<z_stream*>(stream_);
        inflateEnd(zs);
        delete zs;
    }
}

InflateStream::InflateStream(InflateStream&& o) noexcept
    : stream_(o.stream_), bytes_in_(o.bytes_in_), bytes_out_(o.bytes_out_) {
    o.stream_ = nullptr;
}

InflateStream& InflateStream::operator=(InflateStream&& o) noexcept {
    if (this != &o) {
        if (stream_) { auto* zs = static_cast<z_stream*>(stream_); inflateEnd(zs); delete zs; }
        stream_ = o.stream_; o.stream_ = nullptr;
        bytes_in_ = o.bytes_in_; bytes_out_ = o.bytes_out_;
    }
    return *this;
}

std::vector<std::byte> InflateStream::push(const std::byte* data, size_t len) {
    if (!stream_ || !data || len == 0) return {};
    auto* zs = static_cast<z_stream*>(stream_);
    zs->next_in   = reinterpret_cast<Bytef*>(const_cast<std::byte*>(data));
    zs->avail_in  = static_cast<uInt>(len);
    bytes_in_ += len;

    std::vector<std::byte> out;
    const size_t chunk = 65536;

    do {
        size_t old_sz = out.size();
        out.resize(old_sz + chunk);
        zs->next_out  = reinterpret_cast<Bytef*>(out.data()) + old_sz;
        zs->avail_out = static_cast<uInt>(chunk);

        int rc = ::inflate(zs, Z_NO_FLUSH);
        size_t written = chunk - zs->avail_out;
        bytes_out_ += written;
        out.resize(old_sz + written);
        if (rc == Z_STREAM_END || rc == Z_BUF_ERROR) break;
        if (rc != Z_OK) return {};
    } while (zs->avail_out == 0);

    return out;
}

std::vector<std::byte> InflateStream::push(const std::string& data) {
    return push(reinterpret_cast<const std::byte*>(data.data()), data.size());
}

std::vector<std::byte> InflateStream::finish() {
    return {}; // inflate has no explicit finish; data is streamed out as available
}

size_t InflateStream::bytes_in() const { return bytes_in_; }
size_t InflateStream::bytes_out() const { return bytes_out_; }

} // namespace cpp_core::compress