// MINXG C++ demo — compute the 10th Fibonacci number.
#include <iostream>

long long fib(int n) {
    if (n <= 1) return n;
    long long a = 0, b = 1;
    for (int i = 2; i <= n; ++i) {
        long long t = a + b;
        a = b;
        b = t;
    }
    return b;
}

int main() {
    std::cout << "C++ demo: fib(10) = " << fib(10) << std::endl;
    return 0;
}
