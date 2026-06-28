// MINXG C++ bridge — real C++ source.
// Reads a JSON payload from stdin, evaluates a simple arithmetic expression,
// and prints a JSON response. The Python adapter can compile custom code too.
#include <cstdio>
#include <cstring>
#include <cstdlib>

static int eval_expr(const char *expr, long long &out) {
    long long a = 0, b = 0;
    char op = 0;
    if (std::sscanf(expr, "%lld %c %lld", &a, &op, &b) != 3) return -1;
    switch (op) {
        case '+': out = a + b; return 0;
        case '-': out = a - b; return 0;
        case '*': out = a * b; return 0;
        case '/':
            if (b == 0) return -2;
            out = a / b;
            return 0;
    }
    return -1;
}

int main() {
    char line[2048];
    if (!std::fgets(line, sizeof(line), stdin)) {
        std::printf("{\"status\":\"error\",\"stderr\":\"empty payload\"}\n");
        return 1;
    }
    const char *key = "\"code\"";
    char *p = std::strstr(line, key);
    if (!p) {
        std::printf("{\"status\":\"error\",\"stderr\":\"missing code field\"}\n");
        return 1;
    }
    p = std::strchr(p + std::strlen(key), '"');
    if (!p) {
        std::printf("{\"status\":\"error\",\"stderr\":\"malformed code\"}\n");
        return 1;
    }
    ++p;
    char code[1024] = {0};
    size_t i = 0;
    while (*p && *p != '"' && i < sizeof(code) - 1) {
        code[i++] = *p++;
    }
    long long result = 0;
    int err = eval_expr(code, result);
    if (err == -2) {
        std::printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"divide by zero\"}\n");
    } else if (err == -1) {
        std::printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"only simple 'a op b' arithmetic is supported in C++ bridge\"}\n");
    } else {
        std::printf("{\"status\":\"ok\",\"language\":\"cpp\",\"result\":%lld}\n", result);
    }
    return 0;
}
