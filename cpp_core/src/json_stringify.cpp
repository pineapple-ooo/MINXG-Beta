// cpp_core/src/json_stringify.cpp
//
// Flat C-callable JSON facade for cpp_core::json_fast.
//
// Design note: we DO NOT expose the C++ JsonValue (std::variant)
// across the C boundary. That indirection corrupts alignment on
// aarch64 targets that lack strict vtable pointers. Instead we
// round-trip via a heap-allocated std::string that holds the
// serialised form. The C side then uses cpp_json_parse_view() to
// borrow a string_view-like (ptr + len) into stable memory owned
// by the daemon's std::string slot.
//
// The C ABI is:
//
//   parse(text_ptr, text_len, out_ptr, out_len) -> int rc
//        parse text, store the serialised form in *out_ptr / out_len.
//        Returns 0 on success, -1 on parse error.
//   get_string(in_ptr, in_len, key, out_ptr, out_len) -> int rc
//        Look up `key` and copy the value into out if it's a string.
//   get_int(in_ptr, in_len, key, fallback) -> int64
//   get_float(in_ptr, in_len, key, fallback) -> double
//   array_size(in_ptr, in_len) -> size_t
//   array_at_string(in_ptr, in_len, idx, out_ptr, out_len) -> int rc
//
// `in_ptr / in_len` points at UTF-8 JSON bytes owned by the
// caller. We re-parse on every call. The C++ side stays simple
// and well-aligned, and the overhead at one-or-two-call frequency
// is acceptable for the daemon RPC workload.
//
// We do NOT free anything inside this file: the caller owns the
// input bytes and the output bytes. The python side manages those
// buffers.

#define _GNU_SOURCE 1
#include <cstdlib>
#include <cstring>
#include <string>
#include <string_view>

#include "json_fast.hpp"

namespace {

bool serialise_to(const cpp_core::json_fast::JsonValue& jv,
                  char** out_ptr, size_t* out_len) {
    auto s = jv.to_json();
    char* buf = (char*) malloc(s.size() + 1);
    if (!buf) {
        return false;
    }
    memcpy(buf, s.data(), s.size());
    buf[s.size()] = 0;
    *out_ptr = buf;
    *out_len = s.size();
    return true;
}

// Re-parse the input every call. The C++ parser is fast enough
// for RPC workloads (<5 MiB input at >100 MB/s on a low-end ARM).
cpp_core::json_fast::JsonValue parse_or_null(const char* text,
                                             size_t text_len) {
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value()) {
        return cpp_core::json_fast::JsonValue();
    }
    // Move so we don't copy again when the caller serialises it.
    return std::move(result.value());
}

}  // namespace

extern "C" {

int cpp_json_parse(const char* text, size_t text_len,
                   char** out_ptr, size_t* out_len) {
    if (!text || !out_ptr || !out_len) {
        return -1;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value()) {
        return -1;
    }
    if (!serialise_to(result.value(), out_ptr, out_len)) {
        return -1;
    }
    return 0;
}

int cpp_json_get_string(const char* text, size_t text_len,
                        const char* key,
                        char** out_ptr, size_t* out_len) {
    if (!text || !key || !out_ptr || !out_len) {
        return -1;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value() || !result.value().is_object()) {
        return -1;
    }
    auto& obj = result.value().as_object();
    auto it = obj.find(key);
    if (it == obj.end() || !it->second.is_string()) {
        return -1;
    }
    auto& s = it->second.as_string();
    char* buf = (char*) malloc(s.size() + 1);
    if (!buf) {
        return -1;
    }
    memcpy(buf, s.data(), s.size());
    buf[s.size()] = 0;
    *out_ptr = buf;
    *out_len = s.size();
    return 0;
}

int64_t cpp_json_get_int(const char* text, size_t text_len,
                         const char* key, int64_t fallback) {
    if (!text || !key) {
        return fallback;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value() || !result.value().is_object()) {
        return fallback;
    }
    auto& obj = result.value().as_object();
    auto it = obj.find(key);
    if (it == obj.end()) {
        return fallback;
    }
    if (it->second.is_int()) {
        return it->second.as_int();
    }
    if (it->second.is_float()) {
        return (int64_t) it->second.as_float();
    }
    return fallback;
}

double cpp_json_get_float(const char* text, size_t text_len,
                          const char* key, double fallback) {
    if (!text || !key) {
        return fallback;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value() || !result.value().is_object()) {
        return fallback;
    }
    auto& obj = result.value().as_object();
    auto it = obj.find(key);
    if (it == obj.end()) {
        return fallback;
    }
    if (it->second.is_float()) {
        return it->second.as_float();
    }
    if (it->second.is_int()) {
        return (double) it->second.as_int();
    }
    return fallback;
}

int cpp_json_is_object(const char* text, size_t text_len) {
    if (!text) {
        return 0;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value()) {
        return 0;
    }
    return result.value().is_object() ? 1 : 0;
}

int cpp_json_is_array(const char* text, size_t text_len) {
    if (!text) {
        return 0;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value()) {
        return 0;
    }
    return result.value().is_array() ? 1 : 0;
}

size_t cpp_json_array_size(const char* text, size_t text_len) {
    if (!text) {
        return 0;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value() || !result.value().is_array()) {
        return 0;
    }
    return result.value().as_array().size();
}

int cpp_json_array_at_string(const char* text, size_t text_len, size_t idx,
                             char** out_ptr, size_t* out_len) {
    if (!text || !out_ptr || !out_len) {
        return -1;
    }
    std::string_view sv(text, text_len);
    auto result = cpp_core::json_fast::parse(sv);
    if (!result.has_value() || !result.value().is_array()) {
        return -1;
    }
    auto& arr = result.value().as_array();
    if (idx >= arr.size() || !arr[idx].is_string()) {
        return -1;
    }
    auto& s = arr[idx].as_string();
    char* buf = (char*) malloc(s.size() + 1);
    if (!buf) {
        return -1;
    }
    memcpy(buf, s.data(), s.size());
    buf[s.size()] = 0;
    *out_ptr = buf;
    *out_len = s.size();
    return 0;
}

void cpp_json_free(char* p) {
    if (!p) {
        return;
    }
    free(p);
}

}  // extern "C"

extern "C" {

/**
 * Single-call combined parse-and-extract.
 *
 * Inputs: text + text_len and a parallel array of (key,
 * expected_type) tuples to look up. Output: three parallel arrays
 *   - int8_results[out]: negative 0/-1 sentinel
 *   - int_results[out]: int64 values (0 on miss)
 *   - float_results[out]: double values (0 on miss)
 *   - str_results[out]: malloc'd strings (NULL on miss);
 *                        caller frees each via cpp_json_free().
 *
 * Lookup types:
 *   0 = skip this key (unused slot in array)
 *   1 = string
 *   2 = int fallback 0
 *   3 = float fallback 0
 *   4 = int / float fallback encoded as float (split later)
 *
 * Substantial speedup comes from a single parse + a single
 * hashtable traversal that fans out to N readers.
 */
void cpp_json_extract_many(const char* text, size_t text_len,
                           const char* const* keys, const int* types,
                           size_t n,
                           int8_t* str_rcs,
                           char** str_results, size_t* str_lens,
                           int64_t* int_results,
                           double* float_results) {
    if (!text || !keys || !types || n == 0) {
        return;
    }
    std::string_view sv(text, text_len);
    auto parsed = cpp_core::json_fast::parse(sv);
    if (!parsed.has_value()) {
        for (size_t i = 0; i < n; i++) {
            if (str_rcs)      str_rcs[i] = -1;
            if (str_results) str_results[i] = nullptr;
            if (str_lens)    str_lens[i] = 0;
            if (int_results) int_results[i] = 0;
            if (float_results) float_results[i] = 0.0;
        }
        return;
    }
    auto* jv = &parsed.value();
    for (size_t i = 0; i < n; i++) {
        int t = types[i];
        const char* k = keys[i];
        if (str_rcs) str_rcs[i] = -1;
        if (str_results) str_results[i] = nullptr;
        if (str_lens) str_lens[i] = 0;
        if (int_results) int_results[i] = 0;
        if (float_results) float_results[i] = 0.0;
        if (t == 0) {
            continue;
        }
        if (!jv->is_object()) {
            continue;
        }
        auto& obj = jv->as_object();
        auto it = obj.find(k);
        if (it == obj.end()) {
            continue;
        }
        if (t == 1) {
            if (it->second.is_string()) {
                auto& s = it->second.as_string();
                char* buf = (char*) malloc(s.size() + 1);
                if (buf) {
                    memcpy(buf, s.data(), s.size());
                    buf[s.size()] = 0;
                    if (str_results) str_results[i] = buf;
                    if (str_lens) str_lens[i] = s.size();
                    if (str_rcs) str_rcs[i] = 0;
                }
            }
        } else if (t == 2) {
            int64_t v = 0;
            if (it->second.is_int()) v = it->second.as_int();
            else if (it->second.is_float()) v = (int64_t) it->second.as_float();
            if (int_results) int_results[i] = v;
        } else if (t == 3) {
            double v = 0.0;
            if (it->second.is_float()) v = it->second.as_float();
            else if (it->second.is_int()) v = (double) it->second.as_int();
            if (float_results) float_results[i] = v;
        }
    }
}

}  // extern "C"
