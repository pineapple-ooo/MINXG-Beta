/* MINXG C demo — paired computational benchmarks.
 *
 * Output is JSON so the Python adapter / tests can parse it:
 *   {"fib92":7540113804746346429,"prime1M":78498,"lin3":[1,2,3]}
 *
 * This is NOT a hello world; it's a real-numerics bake that any
 * compiler can handle without external libraries.
 */
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* ── Fibonacci via matrix exponentiation O(log n) ────────── */
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
static long long fib(long long n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    Mat2 Q = {{{1,1},{1,0}}};
    Mat2 R = mat2_pow(Q, n - 1);
    return R.a[0][0];
}

/* ── Sieve of Eratosthenes ────────────────────────────────── */
static long prime_count(long n) {
    char *s = calloc((size_t)(n + 1), 1);
    long c = 0;
    for (long i = 2; i <= n; i++) {
        if (!s[i]) { c++; for (long j = i*i; j <= n; j += i) s[j] = 1; }
    }
    free(s);
    return c;
}

/* ── 3x3 linear solve Ax=b via Gaussian elimination ──────── */
static void linsolve3(double A[9], double b[3]) {
    for (int col = 0; col < 3; col++) {
        int piv = col;
        for (int r = col+1; r < 3; r++)
            if (fabs(A[r*3+col]) > fabs(A[piv*3+col])) piv = r;
        for (int j = 0; j < 3; j++) { double t=A[col*3+j]; A[col*3+j]=A[piv*3+j]; A[piv*3+j]=t; }
        double t = b[col]; b[col] = b[piv]; b[piv] = t;
        for (int r = col+1; r < 3; r++) {
            double f = A[r*3+col]/A[col*3+col];
            for (int j = col; j < 3; j++) A[r*3+j] -= f*A[col*3+j];
            b[r] -= f*b[col];
        }
    }
    for (int r = 2; r >= 0; r--) {
        b[r] /= A[r*3+r];
        for (int i = 0; i < r; i++) b[i] -= A[i*3+r]*b[r];
    }
}

int main(void) {
    long long f = fib(92);
    long p = prime_count(1000000);

    /* Solve: [1 2 3; 0 1 4; 5 6 0] x = [14; 13; 9]  =>  x = [1, 2, 3] */
    double A[9] = {1,2,3, 0,1,4, 5,6,0};
    double b[3] = {14, 13, 9};
    linsolve3(A, b);

    printf("{\"fib92\":%lld,\"prime1M\":%ld,\"lin3\":[%.10g,%.10g,%.10g]}\n",
           f, p, b[0], b[1], b[2]);
    return 0;
}
