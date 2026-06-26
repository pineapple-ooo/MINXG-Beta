// pybind11 Python bindings for MINXG C++ Core
// Exposes high-performance C++ tools to Python

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11/chrono.h>
#include <string>
#include <vector>
#include <memory>
#include <optional>

#include "../src/file_ops.hpp"
#include "../src/crypto.hpp"
#include "../src/encoding.hpp"
#include "../src/data_proc.hpp"

namespace py = pybind11;

using namespace cpp_core;

// ============================================================================
// Module: minxg_core
// ============================================================================

PYBIND11_MODULE(minxg_core, m) {
    m.doc() = "MINXG C++ Core — High-performance tools with memory safety";

    // ------------------------------------------------------------------------
    // File Operations
    // ------------------------------------------------------------------------
    py::module file_mod = m.def_submodule("file_ops", "File operations");
    
    file_mod.def("read_text", &file_ops::read_text_fully,
        "Read entire file as UTF-8 text",
        py::arg("path"));
    
    file_mod.def("read_bytes", &file_ops::read_binary_file,
        "Read entire file as bytes",
        py::arg("path"));
    
    file_mod.def("write_text", &file_ops::write_text_file,
        "Write text to file",
        py::arg("path"), py::arg("content") = "");
    
    file_mod.def("write_bytes", &file_ops::write_binary_file,
        "Write bytes to file",
        py::arg("path"), py::arg("data"));
    
    file_mod.def("file_exists", &file_ops::file_exists,
        "Check if file exists",
        py::arg("path"));
    
    file_mod.def("get_file_size", &file_ops::get_file_size,
        "Get file size in bytes",
        py::arg("path"));
    
    file_mod.def("copy_file", &file_ops::copy_file_impl,
        "Copy file from src to dst",
        py::arg("src"), py::arg("dst"));
    
    file_mod.def("list_dir", &file_ops::list_directory,
        "List directory contents",
        py::arg("path"));
    
    file_mod.def("glob", &file_ops::glob_pattern,
        "Glob pattern matching",
        py::arg("path"), py::arg("pattern"));
    
    // ------------------------------------------------------------------------
    // Crypto
    // ------------------------------------------------------------------------
    py::module crypto_mod = m.def_submodule("crypto", "Cryptographic utilities");
    
    crypto_mod.def("sha256", [](std::string_view input) -> std::string {
        auto result = crypto::hash_bytes(
            std::as_bytes(std::span<const char>(input.data(), input.size())),
            crypto::HashAlgorithm::SHA256);
        if (!result) return "";
        return encoding::bytes_to_hex(*result);
    }, "Compute SHA-256 hash", py::arg("input"));
    
    crypto_mod.def("sha512", [](std::string_view input) -> std::string {
        auto result = crypto::hash_bytes(
            std::as_bytes(std::span<const char>(input.data(), input.size())),
            crypto::HashAlgorithm::SHA512);
        if (!result) return "";
        return encoding::bytes_to_hex(*result);
    }, "Compute SHA-512 hash", py::arg("input"));
    
    crypto_mod.def("hmac_sha256", [](std::string_view key, std::string_view input) -> std::string {
        auto k = std::as_bytes(std::span<const char>(key.data(), key.size()));
        auto i = std::as_bytes(std::span<const char>(input.data(), input.size()));
        auto result = crypto::hmac_bytes(k, i, crypto::HashAlgorithm::SHA256);
        if (!result) return "";
        return encoding::bytes_to_hex(*result);
    }, "Compute HMAC-SHA256", py::arg("key"), py::arg("input"));
    
    crypto_mod.def("pbkdf2_sha256", [](std::string_view password, std::string_view salt,
                                       std::size_t iterations, std::size_t key_len) -> std::string {
        auto result = crypto::pbkdf2_sha256(password, salt, iterations, key_len);
        if (!result) return "";
        return encoding::bytes_to_hex(*result);
    }, "PBKDF2-SHA256 key derivation", py::arg("password"), py::arg("salt"),
       py::arg("iterations"), py::arg("key_len"));
    
    crypto_mod.def("secure_random_hex", [](std::size_t bytes) -> std::string {
        auto result = crypto::secure_random_bytes(bytes);
        if (!result) return "";
        return encoding::bytes_to_hex(*result);
    }, "Generate secure random hex string", py::arg("bytes"));
    
    crypto_mod.def("aes256_gcm_encrypt", [](std::string_view plaintext,
                                            const std::string& key_hex,
                                            const std::string& iv_hex) -> py::dict {
        auto key = encoding::hex_to_bytes(key_hex);
        auto iv = encoding::hex_to_bytes(iv_hex);
        if (!key || !iv || key->size() != 32 || iv->size() != 16) {
            PyErr_SetString(PyExc_ValueError, "Invalid key or IV");
            return py::none();
        }
        
        crypto::AesKey k;
        crypto::AesIv i;
        std::memcpy(k.data, key->data(), 32);
        std::memcpy(i.data, iv->data(), 16);
        
        auto ct = crypto::aes256_gcm_encrypt(
            std::as_bytes(std::span<const char>(plaintext.data(), plaintext.size())),
            k, i);
        
        if (!ct) {
            PyErr_SetString(PyExc_RuntimeError, "Encryption failed");
            return py::none();
        }
        
        py::dict result;
        result["ciphertext"] = encoding::bytes_to_hex(ct->ciphertext);
        result["tag"] = encoding::bytes_to_hex(ct->tag);
        return result;
    }, "AES-256-GCM encrypt", py::arg("plaintext"), py::arg("key_hex"), py::arg("iv_hex"));
    
    crypto_mod.def("aes256_gcm_decrypt", [](const std::string& ciphertext_hex,
                                            const std::string& key_hex,
                                            const std::string& iv_hex,
                                            const std::string& tag_hex) -> py::bytes {
        auto ct = encoding::hex_to_bytes(ciphertext_hex);
        auto key = encoding::hex_to_bytes(key_hex);
        auto iv = encoding::hex_to_bytes(iv_hex);
        auto tag = encoding::hex_to_bytes(tag_hex);
        
        if (!ct || !key || !iv || !tag) return py::bytes("");
        
        crypto::AesKey k;
        crypto::AesIv i;
        std::memcpy(k.data, key->data(), 32);
        std::memcpy(i.data, iv->data(), 16);
        
        auto pt = crypto::aes256_gcm_decrypt(*ct, k, i, *tag);
        if (!pt) return py::bytes("");
        
        return py::bytes(reinterpret_cast<const char*>(pt->data()), pt->size());
    }, "AES-256-GCM decrypt", py::arg("ciphertext_hex"), py::arg("key_hex"),
       py::arg("iv_hex"), py::arg("tag_hex"));
    
    // ------------------------------------------------------------------------
    // Encoding
    // ------------------------------------------------------------------------
    py::module enc_mod = m.def_submodule("encoding", "Text/binary encoding");
    
    enc_mod.def("base64_encode", &encoding::base64_encode,
        "Encode bytes to Base64", py::arg("data"));
    
    enc_mod.def("base64_decode", &encoding::base64_decode,
        "Decode Base64 to bytes", py::arg("encoded"));
    
    enc_mod.def("hex_encode", &encoding::bytes_to_hex,
        "Encode bytes to hex string", py::arg("data"));
    
    enc_mod.def("hex_decode", &encoding::hex_to_bytes,
        "Decode hex string to bytes", py::arg("hex"));
    
    enc_mod.def("url_encode", &encoding::url_encode,
        "URL-encode a string", py::arg("value"));
    
    enc_mod.def("url_decode", &encoding::url_decode,
        "URL-decode a string", py::arg("encoded"));
    
    enc_mod.def("is_valid_utf8", &encoding::is_valid_utf8,
        "Check if bytes are valid UTF-8", py::arg("data"));
    
    // ------------------------------------------------------------------------
    // Data Processing
    // ------------------------------------------------------------------------
    py::module data_mod = m.def_submodule("data_proc", "Text data processing");
    
    data_mod.def("tokenize", &data_proc::tokenize,
        "Split string by delimiters", py::arg("input"), py::arg("delimiters"));
    
    data_mod.def("trim", &data_proc::trim,
        "Remove leading/trailing whitespace", py::arg("input"));
    
    data_mod.def("to_lower", &data_proc::to_lower,
        "Convert to lowercase", py::arg("input"));
    
    data_mod.def("to_upper", &data_proc::to_upper,
        "Convert to uppercase", py::arg("input"));
    
    data_mod.def("word_frequency", &data_proc::word_frequency,
        "Count word frequencies", py::arg("input"));
    
    data_mod.def("split_lines", &data_proc::split_lines,
        "Split text into lines", py::arg("input"), py::arg("keep_empty") = false);
    
    data_mod.def("join", &data_proc::join,
        "Join strings with separator", py::arg("parts"), py::arg("separator"));
    
    data_mod.def("truncate", [](std::string_view input, std::size_t max_len) -> std::string {
        return data_proc::truncate(input, max_len);
    }, "Truncate string", py::arg("input"), py::arg("max_len"));
    
    // ------------------------------------------------------------------------
    // Memory stats
    // ------------------------------------------------------------------------
    m.def("get_memory_stats", []() -> py::dict {
        auto stats = Base::get_memory_stats();
        py::dict result;
        result["total_allocations"] = stats.total_allocations;
        result["total_frees"] = stats.total_frees;
        result["current_allocations"] = stats.current_allocations;
        result["peak_allocations"] = stats.peak_allocations;
        return result;
    }, "Get memory allocation statistics");
    
    m.def("reset_memory_stats", &Base::reset_memory_stats,
        "Reset memory statistics");
}