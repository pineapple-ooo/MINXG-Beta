/* Debug test - print actual code flow */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* Forward decl */
int64_t minxg_bmh_search(const uint8_t* h, size_t hl, const uint8_t* n, size_t nl);

/* Pure C version for comparison */
int64_t pure_bmh(const uint8_t* h, size_t hl, const uint8_t* n, size_t nl) {
    size_t skip[256];
    size_t i, j;
    if (!h || !n || hl == 0 || nl == 0 || nl > hl) return -1;
    for (i = 0; i < 256; i++) skip[i] = nl;
    for (i = 0; i < nl - 1; i++) skip[n[i]] = nl - 1 - i;
    i = 0;
    while (i <= hl - nl) {
        for (j = 0; j < nl && h[i+j] == n[j]; j++) {}
        if (j == nl) return (int64_t)i;
        i += skip[h[i + nl - 1]];
    }
    return -1;
}

int main() {
    uint8_t h[] = "hello world";
    uint8_t n[] = "world";
    printf("h=%p hl=%zu\n", h, strlen((char*)h));
    printf("n=%p nl=%zu\n", n, strlen((char*)n));
    printf("h[6]=%c h[7]=%c h[8]=%c h[9]=%c h[10]=%c\n",
           h[6], h[7], h[8], h[9], h[10]);

    int64_t pure = pure_bmh(h, 11, n, 5);
    printf("pure_bmh = %ld\n", (long)pure);

    int64_t lib = minxg_bmh_search(h, 11, n, 5);
    printf("minxg_bmh_search = %ld\n", (long)lib);

    /* Also test with explicit args */
    int64_t r2 = minxg_bmh_search((uint8_t*)h, (size_t)11, (uint8_t*)n, (size_t)5);
    printf("explicit cast = %ld\n", (long)r2);

    return lib == 6 ? 0 : 1;
}
