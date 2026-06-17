// crypto.cpp — SHA-256/512, AES-256-GCM, HMAC-SHA256, PBKDF2 (C++17)
#include "crypto.hpp"
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>
#include <openssl/crypto.h>
#include <cstring>

namespace cpp_core::crypto {

namespace {
[[maybe_unused]] bool init_openssl() {
    static bool done = []{
        OPENSSL_init_crypto(OPENSSL_INIT_LOAD_CRYPTO_STRINGS, nullptr);
        return true;
    }();
    return done;
}
}  // anonymous namespace

// ─── Sha256 ──────────────────────────────────────────────────────────────────
Sha256::Sha256() noexcept : ctx_(nullptr) {
    init_openssl();
    ctx_ = EVP_MD_CTX_new();
    if (ctx_) EVP_DigestInit_ex(static_cast<EVP_MD_CTX*>(ctx_), EVP_sha256(), nullptr);
}

Sha256::~Sha256() {
    if (ctx_) { EVP_MD_CTX_free(static_cast<EVP_MD_CTX*>(ctx_)); ctx_ = nullptr; }
}

Sha256::Sha256(Sha256&& o) noexcept : ctx_(o.ctx_) { o.ctx_ = nullptr; }
Sha256& Sha256::operator=(Sha256&& o) noexcept {
    if (this != &o) {
        if (ctx_) EVP_MD_CTX_free(static_cast<EVP_MD_CTX*>(ctx_));
        ctx_ = o.ctx_; o.ctx_ = nullptr;
    }
    return *this;
}

Sha256& Sha256::update(ConstByteView data) noexcept {
    if (!ctx_ || data.empty()) return *this;
    EVP_DigestUpdate(static_cast<EVP_MD_CTX*>(ctx_),
                      reinterpret_cast<const unsigned char*>(data.ptr), data.len);
    return *this;
}

Sha256Digest Sha256::digest() noexcept {
    Sha256Digest d{};
    if (ctx_) {
        unsigned int len = 0;
        EVP_DigestFinal_ex(static_cast<EVP_MD_CTX*>(ctx_),
                            reinterpret_cast<unsigned char*>(d.data()), &len);
        EVP_MD_CTX_reset(static_cast<EVP_MD_CTX*>(ctx_));
        EVP_DigestInit_ex(static_cast<EVP_MD_CTX*>(ctx_), EVP_sha256(), nullptr);
    }
    return d;
}

Sha256Digest Sha256::hash(ConstByteView data) noexcept {
    Sha256 h;
    h.update(data);
    return h.digest();
}

// ─── Sha512 ──────────────────────────────────────────────────────────────────
Sha512::Sha512() noexcept : ctx_(nullptr) {
    init_openssl();
    ctx_ = EVP_MD_CTX_new();
    if (ctx_) EVP_DigestInit_ex(static_cast<EVP_MD_CTX*>(ctx_), EVP_sha512(), nullptr);
}

Sha512::~Sha512() {
    if (ctx_) { EVP_MD_CTX_free(static_cast<EVP_MD_CTX*>(ctx_)); ctx_ = nullptr; }
}

Sha512::Sha512(Sha512&& o) noexcept : ctx_(o.ctx_) { o.ctx_ = nullptr; }
Sha512& Sha512::operator=(Sha512&& o) noexcept {
    if (this != &o) {
        if (ctx_) EVP_MD_CTX_free(static_cast<EVP_MD_CTX*>(ctx_));
        ctx_ = o.ctx_; o.ctx_ = nullptr;
    }
    return *this;
}

Sha512& Sha512::update(ConstByteView data) noexcept {
    if (!ctx_ || data.empty()) return *this;
    EVP_DigestUpdate(static_cast<EVP_MD_CTX*>(ctx_),
                      reinterpret_cast<const unsigned char*>(data.ptr), data.len);
    return *this;
}

Sha512Digest Sha512::digest() noexcept {
    Sha512Digest d{};
    if (ctx_) {
        unsigned int len = 0;
        EVP_DigestFinal_ex(static_cast<EVP_MD_CTX*>(ctx_),
                            reinterpret_cast<unsigned char*>(d.data()), &len);
        EVP_MD_CTX_reset(static_cast<EVP_MD_CTX*>(ctx_));
        EVP_DigestInit_ex(static_cast<EVP_MD_CTX*>(ctx_), EVP_sha512(), nullptr);
    }
    return d;
}

Sha512Digest Sha512::hash(ConstByteView data) noexcept {
    Sha512 h;
    h.update(data);
    return h.digest();
}

// ─── HMAC-SHA256 ─────────────────────────────────────────────────────────────
std::optional<Sha256Digest> hmac_sha256(ConstByteView key, ConstByteView data) noexcept {
    init_openssl();
    std::optional<Sha256Digest> out = Sha256Digest{};
    unsigned int len = 0;
    unsigned char* result = HMAC(EVP_sha256(),
                  reinterpret_cast<const unsigned char*>(key.ptr), static_cast<int>(key.len),
                  reinterpret_cast<const unsigned char*>(data.ptr), static_cast<int>(data.len),
                  reinterpret_cast<unsigned char*>(out->data()), &len);
    if (!result || len != 32) return std::nullopt;
    return out;
}

// ─── PBKDF2-HMAC-SHA256 ─────────────────────────────────────────────────────
bool pbkdf2_sha256(ConstByteView password, ConstByteView salt,
                   uint32_t iterations, std::byte* output, std::size_t output_len) noexcept {
    init_openssl();
    int ok = PKCS5_PBKDF2_HMAC(
        reinterpret_cast<const char*>(password.ptr),
        static_cast<int>(password.len),
        reinterpret_cast<const unsigned char*>(salt.ptr), static_cast<int>(salt.len),
        iterations, EVP_sha256(),
        static_cast<int>(output_len),
        reinterpret_cast<unsigned char*>(output));
    return ok == 1;
}

// ─── AesCipher ────────────────────────────────────────────────────────────────
AesCipher::AesCipher(Direction dir, const AesKey& key, const AesIv& iv) noexcept
    : dir_(dir), key_(key), iv_(iv) {
    init_openssl();
    ctx_ = EVP_CIPHER_CTX_new();
    if (!ctx_) return;

    const EVP_CIPHER* cipher = EVP_aes_256_gcm();
    auto* k = static_cast<const unsigned char*>(static_cast<const void*>(key_.data()));
    auto* i = static_cast<const unsigned char*>(static_cast<const void*>(iv_.data()));
    int ok;
    if (dir == Direction::Encrypt) {
        ok = EVP_EncryptInit_ex(static_cast<EVP_CIPHER_CTX*>(ctx_), cipher, nullptr, k, i);
    } else {
        ok = EVP_DecryptInit_ex(static_cast<EVP_CIPHER_CTX*>(ctx_), cipher, nullptr, k, i);
    }
    if (!ok) { EVP_CIPHER_CTX_free(static_cast<EVP_CIPHER_CTX*>(ctx_)); ctx_ = nullptr; }
}

AesCipher::~AesCipher() {
    if (ctx_) { EVP_CIPHER_CTX_free(static_cast<EVP_CIPHER_CTX*>(ctx_)); ctx_ = nullptr; }
}

AesCipher::AesCipher(AesCipher&& o) noexcept : ctx_(o.ctx_), dir_(o.dir_), key_(o.key_), iv_(o.iv_) {
    o.ctx_ = nullptr;
}

AesCipher& AesCipher::operator=(AesCipher&& o) noexcept {
    if (this != &o) {
        if (ctx_) EVP_CIPHER_CTX_free(static_cast<EVP_CIPHER_CTX*>(ctx_));
        ctx_ = o.ctx_; o.ctx_ = nullptr;
        dir_ = o.dir_; key_ = o.key_; iv_ = o.iv_;
    }
    return *this;
}

static void reinit_gcm(void* ctx, const AesKey& key, const AesIv& iv, bool encrypt) {
    auto* k = static_cast<const unsigned char*>(static_cast<const void*>(key.data()));
    auto* i = static_cast<const unsigned char*>(static_cast<const void*>(iv.data()));
    if (encrypt)
        EVP_EncryptInit_ex(static_cast<EVP_CIPHER_CTX*>(ctx), EVP_aes_256_gcm(), nullptr, k, i);
    else
        EVP_DecryptInit_ex(static_cast<EVP_CIPHER_CTX*>(ctx), EVP_aes_256_gcm(), nullptr, k, i);
}

std::optional<AesEncryptResult> AesCipher::encrypt(ConstByteView plaintext) noexcept {
    if (!ctx_ || plaintext.empty()) return std::nullopt;
    AesEncryptResult r;
    r.ciphertext.resize(plaintext.len + 16);
    int enc_len = 0;
    int ok = EVP_EncryptUpdate(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(r.ciphertext.data()), &enc_len,
        reinterpret_cast<const unsigned char*>(plaintext.ptr), static_cast<int>(plaintext.len));
    if (!ok) return std::nullopt;
    int final_len = 0;
    ok = EVP_EncryptFinal_ex(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(r.ciphertext.data()) + enc_len, &final_len);
    if (!ok) return std::nullopt;
    r.ciphertext.resize(static_cast<std::size_t>(enc_len) + static_cast<std::size_t>(final_len));
    EVP_CIPHER_CTX_ctrl(static_cast<EVP_CIPHER_CTX*>(ctx_),
                         EVP_CTRL_GCM_GET_TAG, 16, r.tag.data());
    reinit_gcm(ctx_, key_, iv_, true);
    return r;
}

bool AesCipher::encrypt(ConstByteView plaintext, ByteView output, std::byte* out_tag) noexcept {
    if (!ctx_ || plaintext.empty() || output.len < plaintext.len) return false;
    int enc_len = 0;
    int ok = EVP_EncryptUpdate(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(output.ptr), &enc_len,
        reinterpret_cast<const unsigned char*>(plaintext.ptr), static_cast<int>(plaintext.len));
    if (!ok) return false;
    int final_len = 0;
    ok = EVP_EncryptFinal_ex(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(output.ptr) + enc_len, &final_len);
    if (!ok) return false;
    EVP_CIPHER_CTX_ctrl(static_cast<EVP_CIPHER_CTX*>(ctx_),
                         EVP_CTRL_GCM_GET_TAG, 16, out_tag);
    reinit_gcm(ctx_, key_, iv_, true);
    return true;
}

std::optional<std::vector<std::byte>> AesCipher::decrypt(ConstByteView ciphertext, const std::byte* tag) noexcept {
    if (!ctx_ || ciphertext.empty()) return std::nullopt;
    EVP_CIPHER_CTX_ctrl(static_cast<EVP_CIPHER_CTX*>(ctx_),
                         EVP_CTRL_GCM_SET_TAG, 16,
                         const_cast<std::byte*>(tag));
    std::vector<std::byte> out(ciphertext.len);
    int dec_len = 0;
    int ok = EVP_DecryptUpdate(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(out.data()), &dec_len,
        reinterpret_cast<const unsigned char*>(ciphertext.ptr), static_cast<int>(ciphertext.len));
    if (!ok) return std::nullopt;
    int final_len = 0;
    ok = EVP_DecryptFinal_ex(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(out.data()) + dec_len, &final_len);
    if (!ok) return std::nullopt;
    out.resize(static_cast<std::size_t>(dec_len) + static_cast<std::size_t>(final_len));
    reinit_gcm(ctx_, key_, iv_, false);
    return out;
}

bool AesCipher::decrypt(ConstByteView ciphertext, ByteView output, const std::byte* tag) noexcept {
    if (!ctx_ || ciphertext.empty() || output.len < ciphertext.len) return false;
    EVP_CIPHER_CTX_ctrl(static_cast<EVP_CIPHER_CTX*>(ctx_),
                         EVP_CTRL_GCM_SET_TAG, 16,
                         const_cast<std::byte*>(tag));
    int dec_len = 0;
    int ok = EVP_DecryptUpdate(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(output.ptr), &dec_len,
        reinterpret_cast<const unsigned char*>(ciphertext.ptr), static_cast<int>(ciphertext.len));
    if (!ok) return false;
    int final_len = 0;
    ok = EVP_DecryptFinal_ex(
        static_cast<EVP_CIPHER_CTX*>(ctx_),
        reinterpret_cast<unsigned char*>(output.ptr) + dec_len, &final_len);
    if (!ok) return false;
    reinit_gcm(ctx_, key_, iv_, false);
    return true;
}

// ─── Secure random ───────────────────────────────────────────────────────────
bool secure_random_bytes(ByteView buffer) noexcept {
    if (buffer.empty()) return true;
    init_openssl();
    return RAND_bytes(reinterpret_cast<unsigned char*>(buffer.ptr),
                       static_cast<int>(buffer.len)) == 1;
}

void secure_zero(ByteView data) noexcept {
    if (data.empty() || data.ptr == nullptr) return;
    OPENSSL_cleanse(static_cast<void*>(const_cast<std::byte*>(data.ptr)), data.len);
}

// ─── Standalone helpers ───────────────────────────────────────────────────────
Sha256Digest sha256(ConstByteView data) noexcept { return Sha256::hash(data); }
Sha512Digest sha512(ConstByteView data) noexcept { return Sha512::hash(data); }

}  // namespace cpp_core::crypto