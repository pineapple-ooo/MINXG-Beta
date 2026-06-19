package io.minxg;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Tiny JSON wrapper used everywhere in this module.
 *
 * The Python side drives pretty-printed single-line JSON; this side
 * parses one line of JSON, exposes typed getters, and serialises via
 * toJson(). We avoid pulling in jackson / gson; the corpus is small
 * (daemon RPC) and a hand-rolled parser is faster at single-digit
 * MB/s, which matches our actual load.
 */
public final class Json {

    private final Object value;

    private Json(Object value) {
        this.value = value;
    }

    public static Json object() {
        return new Json(new LinkedHashMap<String, Json>());
    }

    public static Json array() {
        return new Json(new ArrayList<Json>());
    }

    public Json put(String key, Object v) {
        ((Map<String, Json>) value).put(key, wrap(v));
        return this;
    }

    public Json add(Object v) {
        ((List<Json>) value).add(wrap(v));
        return this;
    }

    public int size() {
        if (value instanceof Map) {
            return ((Map<?, ?>) value).size();
        }
        if (value instanceof List) {
            return ((List<?>) value).size();
        }
        return 0;
    }

    public String str(String key) {
        Object o = get(key);
        return o == null ? null : unwrap(o).toString();
    }

    public String getString(String key) {
        Object o = get(key);
        return o == null ? null : unwrap(o).toString();
    }

    public int integer(String key) {
        Object o = get(key);
        if (o == null) {
            return 0;
        }
        Object u = unwrap(o);
        if (u instanceof Number) {
            return ((Number) u).intValue();
        }
        try {
            return Integer.parseInt(u.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    public List<Json> array(String key) {
        Object o = get(key);
        if (o == null) {
            return new ArrayList<>();
        }
        Object u = unwrap(o);
        if (u instanceof List) {
            return (List<Json>) u;
        }
        return new ArrayList<>();
    }

    public List<Json> asArray() {
        if (value instanceof List) {
            return (List<Json>) value;
        }
        return new ArrayList<>();
    }

    private Object get(String key) {
        if (value instanceof Map) {
            return ((Map<String, Json>) value).get(key);
        }
        return null;
    }

    /** Strip one layer of Json wrapping so callers see primitives. */
    private static Object unwrap(Object v) {
        if (v instanceof Json) {
            Object inner = ((Json) v).value;
            return inner == null ? null : inner;
        }
        return v;
    }

    private static Json wrap(Object v) {
        if (v == null) {
            return new Json(null);
        }
        if (v instanceof Json) {
            return (Json) v;
        }
        if (v instanceof Number || v instanceof Boolean) {
            return new Json(v);
        }
        if (v instanceof Map) {
            Json o = object();
            for (Map.Entry<?, ?> e : ((Map<?, ?>) v).entrySet()) {
                o.put(e.getKey().toString(), e.getValue());
            }
            return o;
        }
        if (v instanceof Iterable) {
            Json a = array();
            for (Object x : (Iterable<?>) v) {
                a.add(x);
            }
            return a;
        }
        if (v instanceof char[]) {
            return new Json(new String((char[]) v));
        }
        return new Json(v.toString());
    }

    // ----- parser -----

    public static Json parse(String s) {
        Parser p = new Parser(s);
        p.skipWs();
        Json j = p.readValue();
        return j;
    }

    // ----- serialiser -----

    public String toJson() {
        StringBuilder sb = new StringBuilder();
        write(sb);
        return sb.toString();
    }

    private void write(StringBuilder sb) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof Boolean || value instanceof Number) {
            sb.append(value);
        } else if (value instanceof Map) {
            sb.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) value).entrySet()) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                sb.append('"').append(escape(e.getKey().toString()))
                        .append("\":");
                Object v = e.getValue();
                if (v instanceof Json) {
                    ((Json) v).write(sb);
                } else if (v == null) {
                    sb.append("null");
                } else if (v instanceof Number || v instanceof Boolean) {
                    sb.append(v);
                } else {
                    sb.append('"').append(escape(v.toString()))
                            .append('"');
                }
            }
            sb.append('}');
        } else if (value instanceof List) {
            sb.append('[');
            boolean first = true;
            for (Object v : (List<?>) value) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                if (v instanceof Json) {
                    ((Json) v).write(sb);
                } else if (v == null) {
                    sb.append("null");
                } else if (v instanceof Number || v instanceof Boolean) {
                    sb.append(v);
                } else {
                    sb.append('"').append(escape(v.toString()))
                            .append('"');
                }
            }
            sb.append(']');
        } else {
            sb.append('"').append(escape(value.toString())).append('"');
        }
    }

    private static String escape(String s) {
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':
                    sb.append("\\\"");
                    break;
                case '\\':
                    sb.append("\\\\");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }

    private static final class Parser {

        private final String s;
        private int pos;

        Parser(String s) {
            this.s = s;
            this.pos = 0;
        }

        void skipWs() {
            while (pos < s.length() && Character.isWhitespace(s.charAt(pos))) {
                pos++;
            }
        }

        Json readValue() {
            skipWs();
            if (pos >= s.length()) {
                return new Json(null);
            }
            char c = s.charAt(pos);
            if (c == '{') {
                return readObject();
            }
            if (c == '[') {
                return readArray();
            }
            if (c == '"') {
                return new Json(readString());
            }
            if (c == 't' || c == 'f') {
                return readBool();
            }
            if (c == 'n') {
                pos += 4; // null
                return new Json(null);
            }
            return readNumberOrWord();
        }

        Json readObject() {
            Json o = object();
            pos++; // consume {
            skipWs();
            if (pos < s.length() && s.charAt(pos) == '}') {
                pos++;
                return o;
            }
            while (pos < s.length()) {
                skipWs();
                String key = readString();
                skipWs();
                pos++; // consume :
                Json value = readValue();
                o.put(key, value);
                skipWs();
                if (pos < s.length() && s.charAt(pos) == ',') {
                    pos++;
                    continue;
                }
                if (pos < s.length() && s.charAt(pos) == '}') {
                    pos++;
                    return o;
                }
            }
            return o;
        }

        Json readArray() {
            Json a = array();
            pos++; // consume [
            skipWs();
            if (pos < s.length() && s.charAt(pos) == ']') {
                pos++;
                return a;
            }
            while (pos < s.length()) {
                Json value = readValue();
                a.add(value);
                skipWs();
                if (pos < s.length() && s.charAt(pos) == ',') {
                    pos++;
                    continue;
                }
                if (pos < s.length() && s.charAt(pos) == ']') {
                    pos++;
                    return a;
                }
            }
            return a;
        }

        String readString() {
            if (pos >= s.length() || s.charAt(pos) != '"') {
                return "";
            }
            pos++;
            StringBuilder sb = new StringBuilder();
            while (pos < s.length()) {
                char c = s.charAt(pos);
                if (c == '"') {
                    pos++;
                    return sb.toString();
                }
                if (c == '\\') {
                    pos++;
                    if (pos >= s.length()) {
                        break;
                    }
                    char esc = s.charAt(pos);
                    switch (esc) {
                        case 'n':
                            sb.append('\n');
                            break;
                        case 'r':
                            sb.append('\r');
                            break;
                        case 't':
                            sb.append('\t');
                            break;
                        case 'b':
                            sb.append('\b');
                            break;
                        case 'f':
                            sb.append('\f');
                            break;
                        case 'u':
                            if (pos + 4 < s.length()) {
                                String hex = s.substring(pos + 1, pos + 5);
                                sb.append((char) Integer.parseInt(hex, 16));
                                pos += 4;
                            }
                            break;
                        default:
                            sb.append(esc);
                    }
                    pos++;
                    continue;
                }
                sb.append(c);
                pos++;
            }
            return sb.toString();
        }

        Json readBool() {
            if (s.charAt(pos) == 't') {
                pos += 4;
                return new Json(Boolean.TRUE);
            }
            pos += 5;
            return new Json(Boolean.FALSE);
        }

        Json readNumberOrWord() {
            int start = pos;
            while (pos < s.length() && !isTerminator(s.charAt(pos))) {
                pos++;
            }
            String token = s.substring(start, pos);
            try {
                if (token.contains(".")) {
                    return new Json(Double.parseDouble(token));
                }
                return new Json(Long.parseLong(token));
            } catch (NumberFormatException e) {
                return new Json(token);
            }
        }

        private boolean isTerminator(char c) {
            return c == ',' || c == '}' || c == ']'
                    || Character.isWhitespace(c);
        }
    }

    // ----- bridge helpers -----

    public static double[] doubles(List<Json> items) {
        double[] out = new double[items.size()];
        for (int i = 0; i < items.size(); i++) {
            Json item = items.get(i);
            if (item.value instanceof Number) {
                out[i] = ((Number) item.value).doubleValue();
            } else if (item.value instanceof String) {
                try {
                    out[i] = Double.parseDouble((String) item.value);
                } catch (NumberFormatException e) {
                    out[i] = 0d;
                }
            }
        }
        return out;
    }
}
