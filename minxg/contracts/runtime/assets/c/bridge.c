/* MINXG C bridge — real C source.
 * Reads a JSON payload from stdin, evaluates a tiny safe expression via
 * a limited arithmetic evaluator, and prints a JSON response.
 * The Python adapter can also compile custom user C code instead.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

/* Minimal in-process evaluator for "a + b", "a - b", "a * b", "a / b" */
static int eval_expr(const char *expr, long *out) {
    long a = 0, b = 0;
    char op = 0;
    if (sscanf(expr, "%ld %c %ld", &a, &op, &b) != 3) return -1;
    switch (op) {
        case '+': *out = a + b; return 0;
        case '-': *out = a - b; return 0;
        case '*': *out = a * b; return 0;
        case '/':
            if (b == 0) return -2;
            *out = a / b;
            return 0;
    }
    return -1;
}

int main(void) {
    char line[2048];
    if (!fgets(line, sizeof(line), stdin)) {
        printf("{\"status\":\"error\",\"stderr\":\"empty payload\"}\n");
        return 1;
    }
    /* Naively pull the "code" string out of the JSON line. */
    const char *key = "\"code\"";
    char *p = strstr(line, key);
    if (!p) {
        printf("{\"status\":\"error\",\"stderr\":\"missing code field\"}\n");
        return 1;
    }
    p = strchr(p + strlen(key), '"');
    if (!p) {
        printf("{\"status\":\"error\",\"stderr\":\"malformed code\"}\n");
        return 1;
    }
    p++;
    char code[1024] = {0};
    size_t i = 0;
    while (*p && *p != '"' && i < sizeof(code) - 1) {
        code[i++] = *p++;
    }

    long result = 0;
    int err = eval_expr(code, &result);
    if (err == -2) {
        printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"divide by zero\"}\n");
    } else if (err == -1) {
        printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"only simple 'a op b' arithmetic is supported in C bridge\"}\n");
    } else {
        printf("{\"status\":\"ok\",\"language\":\"c\",\"result\":%ld}\n", result);
    }
    return 0;
}
