// crypto.hpp — SHA-256/512, AES-256-GCM, HMAC-SHA256, PBKDF2 (C++17)
#ifndef CRYPTO_HPP
#define CRYPTO_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace cpp_core::crypto {

// ─── Byte Views ───────────────────────────────────────────────────────────────
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

// ─── Digest types ─────────────────────────────────────────────────────────────
using Sha256Digest = std::array<std::byte, 32>;
using Sha512Digest = std::array<std::byte, 64>;
using AesKey = std::array<std::byte, 32>;
using AesIv  = std::array<std::byte, 16>;

// ─── SHA-256 ──────────────────────────────────────────────────────────────────
class Sha256 {
public:
    Sha256() noexcept;
    ~Sha256();
    Sha256(Sha256&& other) noexcept;
    Sha256& operator=(Sha256&& other) noexcept;
    Sha256(const Sha256&) = delete;
    Sha256& operator=(const Sha256&) = delete;

    Sha256& update(ConstByteView data) noexcept;
    Sha256Digest digest() noexcept;
    static Sha256Digest hash(ConstByteView data) noexcept;

private:
    void* ctx_{nullptr};  // EVP_MD_CTX*
};

// ─── SHA-512 ──────────────────────────────────────────────────────────────────
class Sha512 {
public:
    Sha512() noexcept;
    ~Sha512();
    Sha512(Sha512&& other) noexcept;
    Sha512& operator=(Sha512&& other) noexcept;
    Sha512(const Sha512&) = delete;
    Sha512& operator=(const Sha512&) = delete;

    Sha512& update(ConstByteView data) noexcept;
    Sha512Digest digest() noexcept;
    static Sha512Digest hash(ConstByteView data) noexcept;

private:
    void* ctx_{nullptr};  // EVP_MD_CTX*
};

// ─── HMAC-SHA256 ─────────────────────────────────────────────────────────────
std::optional<Sha256Digest> hmac_sha256(
    ConstByteView key, ConstByteView data) noexcept;

// ─── PBKDF2-HMAC-SHA256 ───────────────────────────────────────────────────────
bool pbkdf2_sha256(
    ConstByteView password,
    ConstByteView salt,
    uint32_t iterations,
    std::byte* output,
    std::size_t output_len) noexcept;

// ─── AES-256-GCM ─────────────────────────────────────────────────────────────
struct AesEncryptResult {
    std::vector<std::byte> ciphertext;
    std::array<std::byte, 16> tag;
};

class AesCipher {
public:
    enum class Direction { Encrypt, Decrypt };
    AesCipher(Direction dir, const AesKey& key, const AesIv& iv) noexcept;
    ~AesCipher();
    AesCipher(AesCipher&& other) noexcept;
    AesCipher& operator=(AesCipher&& other) noexcept;
    AesCipher(const AesCipher&) = delete;
    AesCipher& operator=(const AesCipher&) = delete;

    bool is_valid() const noexcept { return ctx_ != nullptr; }
    explicit operator bool() const noexcept { return is_valid(); }

    std::optional<AesEncryptResult> encrypt(ConstByteView plaintext) noexcept;
    bool encrypt(ConstByteView plaintext, ByteView output, std::byte* out_tag) noexcept;
    std::optional<std::vector<std::byte>> decrypt(ConstByteView ciphertext, const std::byte* tag) noexcept;
    bool decrypt(ConstByteView ciphertext, ByteView output, const std::byte* tag) noexcept;

private:
    void* ctx_{nullptr};   // EVP_CIPHER_CTX*
    Direction dir_;
    AesKey key_;
    AesIv iv_;
};

// ─── Secure random ───────────────────────────────────────────────────────────
bool secure_random_bytes(ByteView buffer) noexcept;
void secure_zero(ByteView data) noexcept;

// ─── Standalone helpers ───────────────────────────────────────────────────────
Sha256Digest sha256(ConstByteView data) noexcept;
Sha512Digest sha512(ConstByteView data) noexcept;

}  // namespace cpp_core::crypto

#endif  // CRYPTO_HPP