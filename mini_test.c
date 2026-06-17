/* Minimal test to verify BMH search */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* Our function */
int64_t minxg_bmh_search(const uint8_t* haystack, size_t hay_len,
                         const uint8_t* needle,  size_t needle_len);

int main(void) {
    const uint8_t h[] = "hello world";
    const uint8_t n[] = "world";
    int64_t r = minxg_bmh_search(h, (size_t)11, n, (size_t)5);
    printf("r=%ld\n", (long)r);
    if (r == 6) { printf("PASS\n"); return 0; }
    printf("FAIL: expected 6\n");
    return 1;
}
