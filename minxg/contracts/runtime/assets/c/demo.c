/* MINXG C demo — compute factorial of 10. */
#include <stdio.h>

long factorial(long n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

int main(void) {
    printf("C demo: 10! = %ld\n", factorial(10));
    return 0;
}
