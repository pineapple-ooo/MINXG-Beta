/* Standalone BMH test - compile and link with our object files */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

int64_t minxg_bmh_search(const uint8_t* haystack, size_t hay_len,
                         const uint8_t* needle, size_t needle_len);

int main(void) {
    struct { const char* h; size_t hl; const char* n; size_t nl; int expected; } tests[] = {
        {"hello world", 11, "world", 5, 6},
        {"hello world", 11, "hello", 5, 0},
        {"hello world", 11, "cat", 3, -1},
        {"aaaaaa", 6, "aaa", 3, 0},
        {"abababab", 8, "abab", 4, 0},
        {"xyz123abc", 9, "123", 3, 3},
        {"hello world", 11, "world!", 6, -1},
    };
    int pass = 0, fail = 0;
    size_t i;
    for (i = 0; i < sizeof(tests)/sizeof(tests[0]); i++) {
        int64_t r = minxg_bmh_search((uint8_t*)tests[i].h, tests[i].hl,
                                      (uint8_t*)tests[i].n, tests[i].nl);
        if (r == tests[i].expected) {
            printf("PASS: search(\"%s\", \"%s\") = %ld\n", tests[i].h, tests[i].n, (long)r);
            pass++;
        } else {
            printf("FAIL: search(\"%s\", \"%s\") = %ld, expected %d\n",
                   tests[i].h, tests[i].n, (long)r, tests[i].expected);
            fail++;
        }
    }
    printf("\n%d passed, %d failed\n", pass, fail);
    return fail > 0 ? 1 : 0;
}
