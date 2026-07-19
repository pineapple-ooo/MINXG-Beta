# C Bridge for MINXG
# Compile with: gcc -shared -fPIC -o libcbridge.so c_bridge.c

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

// Matrix multiplication
void matrix_multiply(double *a, double *b, double *c, int n, int m, int p) {
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < p; j++) {
            c[i * p + j] = 0;
            for (int k = 0; k < m; k++) {
                c[i * p + j] += a[i * m + k] * b[k * p + j];
            }
        }
    }
}

// FFT (Cooley-Tukey)
void fft(double *real, double *imag, int n) {
    int j = 0;
    for (int i = 1; i < n - 1; i++) {
        int bit = n >> 1;
        while (j & bit) {
            j ^= bit;
            bit >>= 1;
        }
        j ^= bit;
        if (i < j) {
            double tr = real[i]; real[i] = real[j]; real[j] = tr;
            double ti = imag[i]; imag[i] = imag[j]; imag[j] = ti;
        }
    }
    for (int len = 2; len <= n; len <<= 1) {
        double angle = -2.0 * M_PI / len;
        double wreal = cos(angle);
        double wimag = sin(angle);
        for (int i = 0; i < n; i += len) {
            double ureal = 1.0;
            double uimag = 0.0;
            for (int k = i; k < i + len / 2; k++) {
                int l = k + len / 2;
                double treal = ureal * real[l] - uimag * imag[l];
                double timag = ureal * imag[l] + uimag * real[l];
                real[l] = real[k] - treal;
                imag[l] = imag[k] - timag;
                real[k] += treal;
                imag[k] += timag;
                double t = ureal * wreal - uimag * wimag;
                uimag = ureal * wimag + uimag * wreal;
                ureal = t;
            }
        }
    }
}

// Prime sieve
int* prime_sieve(int limit, int *count) {
    char *is_prime = (char *)calloc(limit + 1, sizeof(char));
    memset(is_prime, 1, limit + 1);
    is_prime[0] = is_prime[1] = 0;

    for (int i = 2; i * i <= limit; i++) {
        if (is_prime[i]) {
            for (int j = i * i; j <= limit; j += i)
                is_prime[j] = 0;
        }
    }

    *count = 0;
    for (int i = 0; i <= limit; i++)
        if (is_prime[i]) (*count)++;

    int *primes = (int *)malloc(*count * sizeof(int));
    int idx = 0;
    for (int i = 0; i <= limit; i++)
        if (is_prime[i]) primes[idx++] = i;

    free(is_prime);
    return primes;
}

// SHA-256 (simplified)
void sha256(const char *input, unsigned char *output) {
    // This is a placeholder - use a proper crypto library in production
    unsigned long hash = 5381;
    int c;
    while ((c = *input++))
        hash = ((hash << 5) + hash) + c;
    memcpy(output, &hash, sizeof(hash));
}

// String utilities
char* str_reverse(const char *str) {
    int len = strlen(str);
    char *rev = (char *)malloc(len + 1);
    for (int i = 0; i < len; i++)
        rev[i] = str[len - 1 - i];
    rev[len] = '\0';
    return rev;
}

int str_is_palindrome(const char *str) {
    int len = strlen(str);
    for (int i = 0; i < len / 2; i++)
        if (str[i] != str[len - 1 - i])
            return 0;
    return 1;
}

// Numerical integration (Simpson's rule)
double simpson_integrate(double (*f)(double), double a, double b, int n) {
    double h = (b - a) / n;
    double sum = f(a) + f(b);
    for (int i = 1; i < n; i++) {
        double x = a + i * h;
        sum += (i % 2 == 0 ? 2 : 4) * f(x);
    }
    return sum * h / 3;
}

// Linear regression
void linear_regression(double *x, double *y, int n, double *slope, double *intercept) {
    double sum_x = 0, sum_y = 0, sum_xy = 0, sum_x2 = 0;
    for (int i = 0; i < n; i++) {
        sum_x += x[i];
        sum_y += y[i];
        sum_xy += x[i] * y[i];
        sum_x2 += x[i] * x[i];
    }
    *slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x);
    *intercept = (sum_y - *slope * sum_x) / n;
}

// Sorting algorithms
void quick_sort(double *arr, int low, int high) {
    if (low < high) {
        double pivot = arr[high];
        int i = low - 1;
        for (int j = low; j < high; j++) {
            if (arr[j] <= pivot) {
                i++;
                double temp = arr[i];
                arr[i] = arr[j];
                arr[j] = temp;
            }
        }
        double temp = arr[i + 1];
        arr[i + 1] = arr[high];
        arr[high] = temp;
        int pi = i + 1;
        quick_sort(arr, low, pi - 1);
        quick_sort(arr, pi + 1, high);
    }
}

void merge_sort(double *arr, int left, int right) {
    if (left < right) {
        int mid = left + (right - left) / 2;
        merge_sort(arr, left, mid);
        merge_sort(arr, mid + 1, right);

        int n1 = mid - left + 1;
        int n2 = right - mid;
        double *L = (double *)malloc(n1 * sizeof(double));
        double *R = (double *)malloc(n2 * sizeof(double));

        for (int i = 0; i < n1; i++) L[i] = arr[left + i];
        for (int j = 0; j < n2; j++) R[j] = arr[mid + 1 + j];

        int i = 0, j = 0, k = left;
        while (i < n1 && j < n2) {
            if (L[i] <= R[j]) arr[k++] = L[i++];
            else arr[k++] = R[j++];
        }
        while (i < n1) arr[k++] = L[i++];
        while (j < n2) arr[k++] = R[j++];

        free(L);
        free(R);
    }
}

// GCD and LCM
int gcd(int a, int b) {
    while (b) {
        int t = b;
        b = a % b;
        a = t;
    }
    return a;
}

int lcm(int a, int b) {
    return (a / gcd(a, b)) * b;
}

// Fibonacci with memoization
long long fibonacci(int n) {
    if (n <= 1) return n;
    long long *memo = (long long *)calloc(n + 1, sizeof(long long));
    memo[0] = 0;
    memo[1] = 1;
    for (int i = 2; i <= n; i++)
        memo[i] = memo[i-1] + memo[i-2];
    long long result = memo[n];
    free(memo);
    return result;
}

// Binary search
int binary_search(double *arr, int n, double target) {
    int left = 0, right = n - 1;
    while (left <= right) {
        int mid = left + (right - left) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target) left = mid + 1;
        else right = mid - 1;
    }
    return -1;
}
