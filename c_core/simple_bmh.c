/* Minimal BMH — hand-verified simple implementation */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int64_t minxg_bmh_search(const uint8_t* haystack, size_t hay_len,
                         const uint8_t* needle, size_t needle_len) {
    if (!haystack || !needle || hay_len == 0 || needle_len == 0)
        return -1;
    if (needle_len > hay_len) return -1;
    
    size_t i;
    for (i = 0; i <= hay_len - needle_len; i++) {
        size_t j;
        for (j = 0; j < needle_len; j++) {
            if (haystack[i + j] != needle[j]) break;
        }
        if (j == needle_len) return (int64_t)i;
    }
    return -1;
}

/* Stub functions so we can link */
void minxg_arch_init(void) {}
