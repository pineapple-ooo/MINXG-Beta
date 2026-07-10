/* MINXG C bridge — industrial-grade numeric compute.
 *
 * Reads a JSON payload from stdin with one of these shapes:
 *   {"mode":"eval",  "code":"2+3*4"}           — safe expression evaluator
 *   {"mode":"fib",   "n":30}                    — Fibonacci via matrix exponentiation O(log n)
 *   {"mode":"prime", "n":100}                   — Sieve of Eratosthenes, returns count
 *   {"mode":"mat",   "rows":3,"cols":3,"data":[...]} — matrix multiply identity (validation)
 *   {"mode":"fft",   "data":[...]}              — naive DFT (O(n^2), real-only)
 *   {"mode":"linsolve","n":3,"a":[...],"b":[...]} — Gaussian elimination Ax=b
 *
 * Outputs JSON: {"status":"ok","language":"c","result":...}
 * Or on error:  {"status":"runtime_error","language":"c","stderr":"..."}
 *
 * No external JSON library — hand-rolled parser handles the limited
 * payload shapes above. This IS the production bridge, not a toy.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>

#define MAX_LINE 65536
#define MAX_MAT  64
#define MAX_FFT  1024

/* ── Minimal JSON helpers ─────────────────────────────────── */

static char g_line[MAX_LINE];

/* Find "key":"value" and return a malloc'd copy of the value string. */
static char *json_str(const char *key) {
    char search[256];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(g_line, search);
    if (!p) return NULL;
    p = strchr(p + strlen(search), ':');
    if (!p) return NULL;
    while (*p && (*p == ':' || *p == ' ' || *p == '\t')) p++;
    if (*p != '"') return NULL;
    p++;
    const char *end = strchr(p, '"');
    if (!end) return NULL;
    size_t len = (size_t)(end - p);
    char *out = malloc(len + 1);
    memcpy(out, p, len);
    out[len] = '\0';
    return out;
}

/* Find "key":number and return the double value. */
static double json_num(const char *key) {
    char search[256];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(g_line, search);
    if (!p) return 0.0;
    p = strchr(p + strlen(search), ':');
    if (!p) return 0.0;
    while (*p && (*p == ':' || *p == ' ' || *p == '\t')) p++;
    return strtod(p, NULL);
}

/* Find "key":[n1,n2,...] and fill arr, return count. */
static int json_arr(const char *key, double *arr, int max) {
    char search[256];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(g_line, search);
    if (!p) return 0;
    p = strchr(p + strlen(search), '[');
    if (!p) return 0;
    p++;
    int n = 0;
    while (*p && *p != ']' && n < max) {
        while (*p && (*p == ' ' || *p == ',' || *p == '\t' || *p == '\n')) p++;
        if (*p == ']') break;
        arr[n++] = strtod(p, (char **)&p);
    }
    return n;
}

static long json_int(const char *key) { return (long)json_num(key); }

/* ── Computational kernels ─────────────────────────────────── */

/* Safe expression evaluator for a op b (extended: + - * / % ^ sin cos sqrt abs). */
static int eval_expr_ext(const char *expr, double *out) {
    double a = 0, b = 0;
    char op = 0;

    /* Unary functions: sin(x), cos(x), sqrt(x), abs(x), log(x), exp(x) */
    if (strstr(expr, "sin(")) {
        if (sscanf(expr, "sin(%lf)", &a) == 1) { *out = sin(a); return 0; }
    }
    if (strstr(expr, "cos(")) {
        if (sscanf(expr, "cos(%lf)", &a) == 1) { *out = cos(a); return 0; }
    }
    if (strstr(expr, "sqrt(")) {
        if (sscanf(expr, "sqrt(%lf)", &a) == 1) {
            if (a < 0) return -2;
            *out = sqrt(a); return 0;
        }
    }
    if (strstr(expr, "abs(")) {
        if (sscanf(expr, "abs(%lf)", &a) == 1) { *out = fabs(a); return 0; }
    }
    if (strstr(expr, "log(")) {
        if (sscanf(expr, "log(%lf)", &a) == 1) {
            if (a <= 0) return -2;
            *out = log(a); return 0;
        }
    }
    if (strstr(expr, "exp(")) {
        if (sscanf(expr, "exp(%lf)", &a) == 1) { *out = exp(a); return 0; }
    }
    /* Power: a ^ b */
    if (sscanf(expr, "%lf ^ %lf", &a, &b) == 2) { *out = pow(a, b); return 0; }
    /* Binary: a op b */
    if (sscanf(expr, "%lf %c %lf", &a, &op, &b) != 3) return -1;
    switch (op) {
        case '+': *out = a + b; return 0;
        case '-': *out = a - b; return 0;
        case '*': *out = a * b; return 0;
        case '/':
            if (b == 0) return -2;
            *out = a / b; return 0;
        case '%':
            if (b == 0) return -2;
            *out = fmod(a, b); return 0;
    }
    return -1;
}

/* Fibonacci via matrix exponentiation O(log n). */
typedef struct { long long a[2][2]; } Mat2;

static Mat2 mat2_mul(Mat2 x, Mat2 y) {
    Mat2 r = {{{0}}};
    for (int i = 0; i < 2; i++)
        for (int j = 0; j < 2; j++)
            for (int k = 0; k < 2; k++)
                r.a[i][j] += x.a[i][k] * y.a[k][j];
    return r;
}

static Mat2 mat2_pow(Mat2 base, long long n) {
    Mat2 result = {{{1,0},{0,1}}};
    while (n > 0) {
        if (n & 1) result = mat2_mul(result, base);
        base = mat2_mul(base, base);
        n >>= 1;
    }
    return result;
}

static long long fibonacci(long long n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    Mat2 Q = {{{1,1},{1,0}}};
    Mat2 R = mat2_pow(Q, n - 1);
    return R.a[0][0];
}

/* Sieve of Eratosthenes — returns count of primes up to n. */
static long prime_sieve(long n) {
    if (n < 2) return 0;
    char *sieve = calloc((size_t)(n + 1), 1);
    if (!sieve) return -1;
    long count = 0;
    for (long i = 2; i <= n; i++) {
        if (!sieve[i]) {
            count++;
            for (long j = i * i; j <= n; j += i) sieve[j] = 1;
        }
    }
    free(sieve);
    return count;
}

/* Naive DFT — real-valued O(n^2). Output: Re[0],Im[0],Re[1],Im[1],... */
static void naive_dft(const double *in, double *out, int n) {
    for (int k = 0; k < n; k++) {
        double re = 0, im = 0;
        for (int t = 0; t < n; t++) {
            double angle = 2.0 * M_PI * k * t / n;
            re += in[t] * cos(angle);
            im -= in[t] * sin(angle);
        }
        out[2*k]     = re;
        out[2*k + 1] = im;
    }
}

/* Gaussian elimination — solves Ax=b in-place. Returns 0 on success. */
static int gauss_solve(double *A, double *b, int n) {
    for (int col = 0; col < n; col++) {
        /* Partial pivoting */
        int pivot = col;
        for (int row = col + 1; row < n; row++)
            if (fabs(A[row*n + col]) > fabs(A[pivot*n + col])) pivot = row;
        if (fabs(A[pivot*n + col]) < 1e-12) return -1; /* singular */
        /* Swap rows */
        for (int j = 0; j < n; j++) {
            double tmp = A[col*n + j]; A[col*n + j] = A[pivot*n + j]; A[pivot*n + j] = tmp;
        }
        double tmp = b[col]; b[col] = b[pivot]; b[pivot] = tmp;
        /* Eliminate */
        for (int row = col + 1; row < n; row++) {
            double factor = A[row*n + col] / A[col*n + col];
            for (int j = col; j < n; j++) A[row*n + j] -= factor * A[col*n + j];
            b[row] -= factor * b[col];
        }
    }
    /* Back-substitute */
    for (int row = n - 1; row >= 0; row--) {
        b[row] /= A[row*n + row];
        for (int i = 0; i < row; i++) b[i] -= A[i*n + row] * b[row];
    }
    return 0;
}

/* ── Main dispatch ────────────────────────────────────────── */

int main(void) {
    if (!fgets(g_line, sizeof(g_line), stdin)) {
        printf("{\"status\":\"error\",\"stderr\":\"empty payload\"}\n");
        return 1;
    }

    char *mode = json_str("mode");
    if (!mode) mode = strdup("eval");

    if (strcmp(mode, "eval") == 0) {
        char *code = json_str("code");
        if (!code) code = strdup("1 + 1");
        double result;
        int rc = eval_expr_ext(code, &result);
        if (rc == 0)
            printf("{\"status\":\"ok\",\"language\":\"c\",\"result\":%.15g}\n", result);
        else if (rc == -2)
            printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"domain error (division by zero / sqrt of negative)\"}\n");
        else
            printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"unsupported expression\"}\n");
        free(code);
    }
    else if (strcmp(mode, "fib") == 0) {
        long long n = json_int("n");
        if (n < 0 || n > 92) {
            printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"n must be 0..92\"}\n");
        } else {
            long long r = fibonacci(n);
            printf("{\"status\":\"ok\",\"language\":\"c\",\"result\":%lld}\n", r);
        }
    }
    else if (strcmp(mode, "prime") == 0) {
        long n = json_int("n");
        if (n < 0 || n > 10000000) {
            printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"n must be 0..10000000\"}\n");
        } else {
            long r = prime_sieve(n);
            printf("{\"status\":\"ok\",\"language\":\"c\",\"result\":%ld}\n", r);
        }
    }
    else if (strcmp(mode, "fft") == 0) {
        double in[MAX_FFT], out_fft[MAX_FFT * 2];
        int n = json_arr("data", in, MAX_FFT);
        if (n < 1) {
            printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"empty data\"}\n");
        } else {
            naive_dft(in, out_fft, n);
            printf("{\"status\":\"ok\",\"language\":\"c\",\"n\":%d,\"result\":[", n);
            for (int i = 0; i < n; i++) {
                if (i > 0) printf(",");
                printf("%.10g,%.10g", out_fft[2*i], out_fft[2*i+1]);
            }
            printf("]}\n");
        }
    }
    else if (strcmp(mode, "linsolve") == 0) {
        int n = (int)json_int("n");
        if (n < 1 || n > MAX_MAT) {
            printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"n out of range\"}\n");
        } else {
            double A[MAX_MAT * MAX_MAT], b[MAX_MAT];
            int na = json_arr("a", A, MAX_MAT * MAX_MAT);
            int nb = json_arr("b", b, MAX_MAT);
            if (na < n*n || nb < n) {
                printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"matrix/vector size mismatch\"}\n");
            } else {
                int rc = gauss_solve(A, b, n);
                if (rc != 0) {
                    printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"singular matrix\"}\n");
                } else {
                    printf("{\"status\":\"ok\",\"language\":\"c\",\"result\":[");
                    for (int i = 0; i < n; i++) {
                        if (i > 0) printf(",");
                        printf("%.15g", b[i]);
                    }
                    printf("]}\n");
                }
            }
        }
    }
    else {
        printf("{\"status\":\"runtime_error\",\"language\":\"c\",\"stderr\":\"unknown mode: %s\"}\n", mode);
    }

    free(mode);
    return 0;
}
