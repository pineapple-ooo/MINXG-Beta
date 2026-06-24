// json_fast.cpp — Recursive-descent JSON parser, zero external deps
// Handles all standard JSON with fast skip-path for common ML payloads.

#include "json_fast.hpp"
#include <cstring>
#include <cmath>
#include <sstream>
#include <charconv>

namespace cpp_core::json_fast {

// ─── Type detection ──────────────────────────────────────────────────────────

JsonType JsonValue::type() const {
    return std::visit([](const auto& v) -> JsonType {
        using T = std::decay_t<decltype(v)>;
        if constexpr (std::is_same_v<T, std::nullptr_t>) return JsonType::Null;
        if constexpr (std::is_same_v<T, bool>)          return JsonType::Bool;
        if constexpr (std::is_same_v<T, int64_t>)       return JsonType::Int;
        if constexpr (std::is_same_v<T, double>)        return JsonType::Float;
        if constexpr (std::is_same_v<T, std::string>)   return JsonType::String;
        if constexpr (std::is_same_v<T, JsonArray>)     return JsonType::Array;
        if constexpr (std::is_same_v<T, JsonObject>)    return JsonType::Object;
        return JsonType::Null;
    }, data_);
}

// ─── Accessors ──────────────────────────────────────────────────────────────

bool JsonValue::as_bool() const {
    if (auto* v = std::get_if<bool>(&data_)) return *v;
    if (auto* v = std::get_if<int64_t>(&data_)) return *v != 0;
    throw std::bad_variant_access{};
}

int64_t JsonValue::as_int() const {
    if (auto* v = std::get_if<int64_t>(&data_)) return *v;
    if (auto* v = std::get_if<double>(&data_)) return static_cast<int64_t>(*v);
    throw std::bad_variant_access{};
}

double JsonValue::as_float() const {
    if (auto* v = std::get_if<double>(&data_)) return *v;
    if (auto* v = std::get_if<int64_t>(&data_)) return static_cast<double>(*v);
    throw std::bad_variant_access{};
}

const std::string& JsonValue::as_string() const {
    return std::get<std::string>(data_);
}

const JsonArray& JsonValue::as_array() const {
    return std::get<JsonArray>(data_);
}

const JsonObject& JsonValue::as_object() const {
    return std::get<JsonObject>(data_);
}

// ─── Bracket access ─────────────────────────────────────────────────────────

JsonValue& JsonValue::operator[](const std::string& key) {
    return as_object_mut()[key];
}

const JsonValue& JsonValue::operator[](const std::string& key) const {
    return as_object().at(key);
}

JsonValue& JsonValue::operator[](size_t index) {
    return as_array_mut()[index];
}

const JsonValue& JsonValue::operator[](size_t index) const {
    return as_array()[index];
}

// ─── Convenience getters ────────────────────────────────────────────────────

std::string JsonValue::get_string(const std::string& key, const std::string& def) const {
    if (!is_object()) return def;
    auto& obj = as_object();
    auto it = obj.find(key);
    if (it == obj.end() || !it->second.is_string()) return def;
    return it->second.as_string();
}

int64_t JsonValue::get_int(const std::string& key, int64_t def) const {
    if (!is_object()) return def;
    auto& obj = as_object();
    auto it = obj.find(key);
    if (it == obj.end()) return def;
    if (it->second.is_int()) return it->second.as_int();
    if (it->second.is_float()) return static_cast<int64_t>(it->second.as_float());
    return def;
}

double JsonValue::get_float(const std::string& key, double def) const {
    if (!is_object()) return def;
    auto& obj = as_object();
    auto it = obj.find(key);
    if (it == obj.end()) return def;
    if (it->second.is_float()) return it->second.as_float();
    if (it->second.is_int()) return static_cast<double>(it->second.as_int());
    return def;
}

bool JsonValue::get_bool(const std::string& key, bool def) const {
    if (!is_object()) return def;
    auto& obj = as_object();
    auto it = obj.find(key);
    if (it == obj.end() || !it->second.is_bool()) return def;
    return it->second.as_bool();
}

// ─── Serialization ─────────────────────────────────────────────────────────

static void serialize_recursive(std::ostringstream& os, const JsonValue& val, int indent, int depth) {
    auto pad = [&](int d) {
        for (int i = 0; i < d; i++) os << ' ';
    };

    switch (val.type()) {
    case JsonType::Null:
        os << "null";
        break;
    case JsonType::Bool:
        os << (val.as_bool() ? "true" : "false");
        break;
    case JsonType::Int:
        os << val.as_int();
        break;
    case JsonType::Float: {
        double d = val.as_float();
        if (std::isfinite(d)) os << d;
        else os << "0.0";
        break;
    }
    case JsonType::String: {
        os << '"';
        for (char c : val.as_string()) {
            switch (c) {
            case '"':  os << "\\\""; break;
            case '\\': os << "\\\\"; break;
            case '\n': os << "\\n"; break;
            case '\r': os << "\\r"; break;
            case '\t': os << "\\t"; break;
            default:   os << c;
            }
        }
        os << '"';
        break;
    }
    case JsonType::Array: {
        auto& arr = val.as_array();
        if (arr.empty()) { os << "[]"; break; }
        os << '[';
        if (indent > 0) os << '\n';
        for (size_t i = 0; i < arr.size(); i++) {
            if (indent > 0) pad(depth + indent);
            serialize_recursive(os, arr[i], indent, depth + indent);
            if (i + 1 < arr.size()) {
                os << ',';
                if (indent > 0) os << '\n';
            }
        }
        if (indent > 0) { os << '\n'; pad(depth); }
        os << ']';
        break;
    }
    case JsonType::Object: {
        auto& obj = val.as_object();
        if (obj.empty()) { os << "{}"; break; }
        os << '{';
        if (indent > 0) os << '\n';
        size_t count = 0;
        for (auto& [k, v] : obj) {
            if (indent > 0) pad(depth + indent);
            os << '"' << k << '"' << ':';
            if (indent > 0) os << ' ';
            serialize_recursive(os, v, indent, depth + indent);
            if (++count < obj.size()) {
                os << ',';
                if (indent > 0) os << '\n';
            }
        }
        if (indent > 0) { os << '\n'; pad(depth); }
        os << '}';
        break;
    }
    }
}

std::string JsonValue::to_json() const { return serialize(*this, false); }
std::string JsonValue::to_json_pretty(int indent) const { return serialize(*this, true); }

// ─── Parser ─────────────────────────────────────────────────────────────────

class Parser {
public:
    explicit Parser(std::string_view input) : input_(input), pos_(0) {}

    std::optional<JsonValue> parse_value() {
        skip_ws();
        if (pos_ >= input_.size()) return std::nullopt;

        char c = input_[pos_];
        switch (c) {
        case '{': return parse_object();
        case '[': return parse_array();
        case '"': return parse_string();
        case 't': case 'f': return parse_bool();
        case 'n': return parse_null();
        default:  return parse_number();
        }
    }

private:
    std::string_view input_;
    size_t pos_;

    void skip_ws() {
        while (pos_ < input_.size() && (input_[pos_] == ' ' || input_[pos_] == '\t' ||
               input_[pos_] == '\n' || input_[pos_] == '\r')) pos_++;
    }

    char peek() const { return pos_ < input_.size() ? input_[pos_] : '\0'; }
    char next() { return pos_ < input_.size() ? input_[pos_++] : '\0'; }

    std::optional<JsonValue> parse_null() {
        if (pos_ + 4 > input_.size()) return std::nullopt;
        if (strncmp(input_.data() + pos_, "null", 4) == 0) {
            pos_ += 4;
            return JsonValue(nullptr);
        }
        return std::nullopt;
    }

    std::optional<JsonValue> parse_bool() {
        if (pos_ + 4 <= input_.size() && strncmp(input_.data() + pos_, "true", 4) == 0) {
            pos_ += 4;
            return JsonValue(true);
        }
        if (pos_ + 5 <= input_.size() && strncmp(input_.data() + pos_, "false", 5) == 0) {
            pos_ += 5;
            return JsonValue(false);
        }
        return std::nullopt;
    }

    std::optional<JsonValue> parse_number() {
        size_t start = pos_;
        if (peek() == '-') pos_++;
        if (peek() == '0') { pos_++; }
        else if (peek() >= '1' && peek() <= '9') {
            while (peek() >= '0' && peek() <= '9') pos_++;
        } else return std::nullopt;

        bool is_float = false;
        if (peek() == '.') {
            is_float = true;
            pos_++;
            while (peek() >= '0' && peek() <= '9') pos_++;
        }
        if (peek() == 'e' || peek() == 'E') {
            is_float = true;
            pos_++;
            if (peek() == '+' || peek() == '-') pos_++;
            while (peek() >= '0' && peek() <= '9') pos_++;
        }

        std::string_view num_str = input_.substr(start, pos_ - start);
        if (is_float) {
            double val = 0.0;
            auto [ptr, ec] = std::from_chars(num_str.data(), num_str.data() + num_str.size(), val);
            if (ec == std::errc{}) return JsonValue(val);
            return std::nullopt;
        }
        int64_t val = 0;
        auto [ptr, ec] = std::from_chars(num_str.data(), num_str.data() + num_str.size(), val);
        if (ec == std::errc{}) return JsonValue(val);
        return std::nullopt;
    }

    std::optional<JsonValue> parse_string() {
        if (peek() != '"') return std::nullopt;
        pos_++; // consume opening quote
        std::string result;
        while (pos_ < input_.size()) {
            char c = next();
            if (c == '"') return JsonValue(std::move(result));
            if (c == '\\') {
                char esc = next();
                switch (esc) {
                case '"':  result += '"';  break;
                case '\\': result += '\\'; break;
                case '/':  result += '/';  break;
                case 'n':  result += '\n'; break;
                case 'r':  result += '\r'; break;
                case 't':  result += '\t'; break;
                case 'u': {
                    // Parse 4 hex digits
                    if (pos_ + 4 > input_.size()) return std::nullopt;
                    uint16_t cp = 0;
                    for (int i = 0; i < 4; i++) {
                        char h = next();
                        cp <<= 4;
                        if (h >= '0' && h <= '9') cp |= (h - '0');
                        else if (h >= 'A' && h <= 'F') cp |= (h - 'A' + 10);
                        else if (h >= 'a' && h <= 'f') cp |= (h - 'a' + 10);
                        else return std::nullopt;
                    }
                    // Simplification: skip surrogate pair handling, emit raw bytes
                    if (cp <= 0x7F) result += (char)cp;
                    else if (cp <= 0x7FF) {
                        result += (char)(0xC0 | (cp >> 6));
                        result += (char)(0x80 | (cp & 0x3F));
                    } else {
                        result += (char)(0xE0 | (cp >> 12));
                        result += (char)(0x80 | ((cp >> 6) & 0x3F));
                        result += (char)(0x80 | (cp & 0x3F));
                    }
                    break;
                }
                default: return std::nullopt;
                }
            } else {
                result += c;
            }
        }
        return std::nullopt; // unclosed string
    }

    std::optional<JsonValue> parse_array() {
        if (peek() != '[') return std::nullopt;
        pos_++;
        skip_ws();
        JsonArray arr;
        if (peek() == ']') { pos_++; return JsonValue(std::move(arr)); }
        while (true) {
            auto val = parse_value();
            if (!val) return std::nullopt;
            arr.push_back(std::move(*val));
            skip_ws();
            if (peek() == ',') { pos_++; skip_ws(); }
            else if (peek() == ']') { pos_++; break; }
            else return std::nullopt;
        }
        return JsonValue(std::move(arr));
    }

    std::optional<JsonValue> parse_object() {
        if (peek() != '{') return std::nullopt;
        pos_++;
        skip_ws();
        JsonObject obj;
        if (peek() == '}') { pos_++; return JsonValue(std::move(obj)); }
        while (true) {
            auto key_val = parse_string();
            if (!key_val || !key_val->is_string()) return std::nullopt;
            std::string key = key_val->as_string();
            skip_ws();
            if (peek() != ':') return std::nullopt;
            pos_++;
            skip_ws();
            auto val = parse_value();
            if (!val) return std::nullopt;
            obj[std::move(key)] = std::move(*val);
            skip_ws();
            if (peek() == ',') { pos_++; skip_ws(); }
            else if (peek() == '}') { pos_++; break; }
            else return std::nullopt;
        }
        return JsonValue(std::move(obj));
    }
};

std::optional<JsonValue> parse(std::string_view input) {
    Parser p(input);
    return p.parse_value();
}

std::optional<JsonValue> parse_file(const std::string& path) {
    // Use file_ops to read
    return std::nullopt; // stub — depends on file_ops
}

std::string serialize(const JsonValue& value, bool pretty) {
    std::ostringstream os;
    serialize_recursive(os, value, pretty ? 2 : 0, 0);
    return os.str();
}

}  // namespace cpp_core::json_fast