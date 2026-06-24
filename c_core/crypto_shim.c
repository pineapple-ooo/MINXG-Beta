/*
 * crypto_shim.c — C shims for C++ core interop
 * Provides: minxg_sha256, minxg_hmac_sha256, minxg_pbkdf2_sha256
 *           minxg_base64_encode, minxg_base64_decode
 *           minxg_compress, minxg_decompress, minxg_json_parse, minxg_data_hash
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/sha.h>
#include <openssl/bio.h>
#include <openssl/bn.h>
#include <openssl/rand.h>
#include <zlib.h>
#include "text_engine.h"
#include "minxg_arch.h"

/* ═══ SHA-256 (EVP) ════════════════════════════════════════════════════════ */

int64_t minxg_sha256(const uint8_t* in, size_t in_len, uint8_t* out, size_t out_cap) {
    if (!in || !out || out_cap < 32) return -1;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    if (!ctx) return -1;
    unsigned int out_len = 0;
    int ok = EVP_DigestInit_ex(ctx, EVP_sha256(), NULL)
           && EVP_DigestUpdate(ctx, in, in_len)
           && EVP_DigestFinal_ex(ctx, out, &out_len);
    EVP_MD_CTX_free(ctx);
    return ok ? (int64_t)out_len : -1;
}

/* ═══ HMAC-SHA256 ═══════════════════════════════════════════════════════════ */

int64_t minxg_hmac_sha256(const uint8_t* key, size_t key_len,
                          const uint8_t* in, size_t in_len,
                          uint8_t* out, size_t out_cap) {
    if (!key || !in || !out || out_cap < 32) return -1;
    unsigned int ol = 0;
    uint8_t buf[32];
    if (!HMAC(EVP_sha256(), key, (int)key_len, in, in_len, buf, &ol)) return -1;
    if ((size_t)ol > out_cap) return -1;
    memcpy(out, buf, ol);
    return (int64_t)ol;
}

/* ═══ PBKDF2-SHA256 ════════════════════════════════════════════════════════ */

int minxg_pbkdf2_sha256(const uint8_t* pass, size_t pass_len,
                        const uint8_t* salt, size_t salt_len,
                        int iterations,
                        uint8_t* out, size_t out_len) {
    if (!pass || !salt || !out || iterations <= 0 || out_len == 0) return 0;
    return PKCS5_PBKDF2_HMAC((const char*)pass, (int)pass_len,
                              salt, (int)salt_len,
                              iterations, EVP_sha256(),
                              (int)out_len, out) ? 1 : 0;
}

/* ═══ Base64 (EVP_EncodeBlock — no NL, simple) ════════════════════════════ */

int64_t minxg_base64_encode(const uint8_t* in, size_t in_len,
                            uint8_t* out, size_t out_cap) {
    if (!in || !out) return -1;
    /* EVP_EncodeBlock: output is 4*((in_len+2)/3) + 1. Require at least that. */
    size_t needed = ((in_len + 2) / 3) * 4 + 1;
    if (out_cap < needed) return -1;
    /* EVP_EncodeBlock takes unsigned long*, cast safely for our sizes */
    unsigned long written = EVP_EncodeBlock(out, in, (unsigned long)in_len);
    return (int64_t)written;
}

int64_t minxg_base64_decode(const uint8_t* in, size_t in_len,
                            uint8_t* out, size_t out_cap) {
    if (!in || !out) return -1;
    /* EVP_DecodeBlock: output is up to in_len * 3/4 */
    unsigned long written = EVP_DecodeBlock(out, in, (unsigned long)in_len);
    if ((long)written < 0) return -1;
    /* Remove any padding bytes EVP adds */
    if (in_len > 0) {
        int pad = 0;
        const uint8_t* p = in + in_len - 1;
        while (p >= in && *p == '=') { pad++; p--; }
        if (pad > 0 && (size_t)written >= (size_t)pad)
            written -= (unsigned long)pad;
    }
    return (int64_t)written;
}

/* ═══ Compress/Decompress (zlib) ═══════════════════════════════════════════ */

static int64_t _compress_impl(const uint8_t* in, size_t in_len,
                              uint8_t* out, size_t out_cap, int compress) {
    if (!in || !out) return -1;
    z_stream zs;
    memset(&zs, 0, sizeof(zs));
    int ret;
    if (compress) {
        ret = deflateInit2(&zs, Z_DEFAULT_COMPRESSION, Z_DEFLATED, 15, 8, Z_DEFAULT_STRATEGY);
        if (ret != Z_OK) return -1;
        zs.next_in = (Bytef*)in;
        zs.avail_in = (uInt)in_len;
        zs.next_out = out;
        zs.avail_out = (uInt)out_cap;
        ret = deflate(&zs, Z_FINISH);
        deflateEnd(&zs);
        if (ret != Z_STREAM_END) return -1;
        return (int64_t)zs.total_out;
    } else {
        ret = inflateInit2(&zs, 15 + 16);
        if (ret != Z_OK) return -1;
        zs.next_in = (Bytef*)in;
        zs.avail_in = (uInt)in_len;
        zs.next_out = out;
        zs.avail_out = (uInt)out_cap;
        ret = inflate(&zs, Z_FINISH);
        inflateEnd(&zs);
        if (ret != Z_STREAM_END && ret != Z_OK) return -1;
        return (int64_t)zs.total_out;
    }
}

int64_t minxg_compress(const uint8_t* in, size_t in_len,
                       uint8_t* out, size_t* out_len) {
    int64_t r = _compress_impl(in, in_len, out, *out_len, 1);
    if (r >= 0) *out_len = (size_t)r;
    return r;
}

int64_t minxg_decompress(const uint8_t* in, size_t in_len,
                         uint8_t* out, size_t* out_len) {
    int64_t r = _compress_impl(in, in_len, out, *out_len, 0);
    if (r >= 0) *out_len = (size_t)r;
    return r;
}

/* ═══ JSON validate (minimal) ═══════════════════════════════════════════════ */

bool minxg_json_parse(const char* json_str) {
    if (!json_str) return false;
    const char* s = json_str;
    while (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r') s++;
    return (*s == '{' || *s == '[');
}

/* ═══ Data hash (fast, OpenSSL-based) ══════════════════════════════════════ */

uint64_t minxg_data_hash(const void* data, size_t len) {
    if (!data || len == 0) return 0;
    uint8_t buf[32];
    SHA256((const uint8_t*)data, len, buf);
    uint64_t h = 0;
    for (int i = 0; i < 8; i++) h = h * 33 + buf[i];
    return h;
}
