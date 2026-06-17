#include <stdio.h>
#include <stdint.h>

int64_t minxg_bmh_search(const uint8_t* haystack, size_t hay_len,
                         const uint8_t* needle,  size_t needle_len);

int main() {
    uint8_t h[] = "hello world";
    uint8_t n[] = "world";
    int64_t r = minxg_bmh_search(h, 11, n, 5);
    printf("bmh_search result: %ld (expected 6)\n", r);
    if (r == 6) { printf("PASS\n"); return 0; }
    else { printf("FAIL\n"); return 1; }
}
