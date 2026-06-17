// json_fast.hpp — SIMD-accelerated JSON parser (C++17)
// Zero-copy where possible, skips validation for trusted input.
// Designed for the ML inference pipeline: parse configs, prompts, tool schemas.

#ifndef MINXG_JSON_FAST_HPP
#define MINXG_JSON_FAST_HPP

#include <string>
#include <string_view>
#include <vector>
#include <variant>
#include <unordered_map>
#include <optional>
#include <cstdint>

namespace cpp_core::json_fast {

enum class JsonType {
    Null, Bool, Int, Float, String, Array, Object
};

// Forward-declare
class JsonValue;

using JsonObject = std::unordered_map<std::string, JsonValue>;
using JsonArray  = std::vector<JsonValue>;
using JsonData   = std::variant<
    std::nullptr_t, bool, int64_t, double,
    std::string, JsonArray, JsonObject>;

class JsonValue {
public:
    JsonValue() : data_(nullptr) {}
    JsonValue(std::nullptr_t) : data_(nullptr) {}
    JsonValue(bool v) : data_(v) {}
    JsonValue(int64_t v) : data_(v) {}
    JsonValue(int v) : data_(static_cast<int64_t>(v)) {}
    JsonValue(double v) : data_(v) {}
    JsonValue(std::string v) : data_(std::move(v)) {}
    JsonValue(const char* v) : data_(std::string(v)) {}
    JsonValue(JsonArray v) : data_(std::move(v)) {}
    JsonValue(JsonObject v) : data_(std::move(v)) {}

    JsonType type() const;
    bool is_null()    const { return type() == JsonType::Null; }
    bool is_bool()    const { return type() == JsonType::Bool; }
    bool is_int()     const { return type() == JsonType::Int; }
    bool is_float()   const { return type() == JsonType::Float; }
    bool is_string()  const { return type() == JsonType::String; }
    bool is_array()   const { return type() == JsonType::Array; }
    bool is_object()  const { return type() == JsonType::Object; }

    // Accessors (throws std::bad_variant_access on type mismatch)
    bool            as_bool()    const;
    int64_t         as_int()     const;
    double          as_float()   const;
    const std::string& as_string() const;
    const JsonArray&   as_array()  const;
    const JsonObject&  as_object() const;

    // Mutable access
    JsonArray&  as_array_mut()  { return std::get<JsonArray>(data_); }
    JsonObject& as_object_mut() { return std::get<JsonObject>(data_); }

    // Bracket access for objects and arrays
    JsonValue& operator[](const std::string& key);
    const JsonValue& operator[](const std::string& key) const;
    JsonValue& operator[](size_t index);
    const JsonValue& operator[](size_t index) const;

    // Convenience: get with default
    std::string get_string(const std::string& key, const std::string& def = "") const;
    int64_t     get_int(const std::string& key, int64_t def = 0) const;
    double      get_float(const std::string& key, double def = 0.0) const;
    bool        get_bool(const std::string& key, bool def = false) const;

    // Serialize back to compact JSON
    std::string to_json() const;
    std::string to_json_pretty(int indent = 2) const;

private:
    JsonData data_;
};

// Parse JSON from string_view. Returns nullopt on parse error.
std::optional<JsonValue> parse(std::string_view input);

// Parse JSON from file (memory-mapped internally)
std::optional<JsonValue> parse_file(const std::string& path);

// Serialize to string
std::string serialize(const JsonValue& value, bool pretty = false);

}  // namespace cpp_core::json_fast

#endif  // MINXG_JSON_FAST_HPP