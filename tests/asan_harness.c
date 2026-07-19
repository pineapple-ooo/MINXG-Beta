/* asan_harness.c — exercise every C API uncovered under ASan */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "minxg_arch.h"
#include "mem_pool.h"
#include "text_engine.h"
#include "minxg_evolve.h"

extern char* cpp_url_encode(const char* in);
extern char* cpp_url_decode(const char* in);
extern void  cpp_free(char* s);
extern int   cpp_sha256(const unsigned char* in, unsigned long in_len,
                        unsigned char* out, unsigned long out_cap);
extern int   cpp_tokenize(const char* in, unsigned long in_len,
                          char** out, unsigned long out_cap);
extern void  cpp_free_string_array(char** arr, int len);

#define ARR_SZ 16

int main(void) {
    /* arena */
    minxg_arena_t a = minxg_arena_create(8192);
    assert(a);
    for (int i = 0; i < 50; i++) {
        void* p1 = minxg_arena_alloc(a, 80);
        void* p2 = minxg_arena_alloc(a, 200);
        assert(p1); assert(p2);
        memset(p1, 0xaa, 80);
        memset(p2, 0xbb, 200);
        minxg_arena_reset(a);
    }
    minxg_arena_destroy(a);

    /* slab */
    minxg_slab_t s = minxg_slab_create(40, 16);
    assert(s);
    void* items[8];
    for (int i = 0; i < 8; i++) {
        items[i] = minxg_slab_alloc(s);
        assert(items[i]);
        memset(items[i], 0xcd, 40);
    }
    for (int i = 0; i < 8; i++) minxg_slab_free(s, items[i]);
    /* realloc/free cycle 5 times */
    for (int cycle = 0; cycle < 5; cycle++) {
        void* t[20];
        for (int i = 0; i < 20; i++) t[i] = minxg_slab_alloc(s);
        assert(t[0]);
        for (int i = 0; i < 20; i++) minxg_slab_free(s, t[i]);
    }
    minxg_slab_destroy(s);

    /* ring buffer */
    minxg_rb_t rb = minxg_rb_create(8, 4);
    assert(rb);
    unsigned char in[8]  = {1,2,3,4,5,6,7,8};
    unsigned char out[8] = {0};
    int rc;
    rc = minxg_rb_push(rb, in);  assert(rc == 0);
    rc = minxg_rb_pop(rb, out);  assert(rc == 0);
    /* fill to capacity, expect overflow */
    for (int i = 0; i < 20; i++) {
        rc = minxg_rb_push(rb, in);
        if (rc == 0) {
            rc = minxg_rb_pop(rb, out);
            assert(rc == 0);
        } else {
            /* expected full -> real pop should still drain by exactly one */
            break;
        }
    }
    minxg_rb_destroy(rb);

    /* text engine statistics — uses malloc internally for median copy */
    double vals[16] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
    double mean=0, std=0, med=0, mn=0, mx=0, sum=0;
    rc = minxg_statistics(vals, 16, &mean, &std, &med, &mn, &mx, &sum);
    assert(rc == 0);
    assert(mean == 8.5);
    assert(sum == 136.0);

    /* cpp_wrapper.c — heap alloc + free */
    char* enc = cpp_url_encode("hello world & friends!");
    assert(enc && strcmp(enc, "hello%20world%20%26%20friends!") == 0);
    cpp_free(enc);

    char* dec = cpp_url_decode("hello%20world%20%26%20friends!");
    assert(dec && strcmp(dec, "hello world & friends!") == 0);
    cpp_free(dec);

    unsigned char h[32];
    rc = cpp_sha256((const unsigned char*)"hello world", 11, h, 32);
    assert(rc == 0);

    char* arr[16] = {0};
    int n = cpp_tokenize("the quick brown fox jumps", 25, arr, 16);
    assert(n == 5);
    cpp_free_string_array(arr, n);

    /* NCD pair */
    unsigned char a5[5] = {1,2,3,4,5};
    unsigned char b5[5] = {2,3,4,5,6};
    double v = minxg_evolve_ncd_v1(a5, 5, b5, 5);
    printf("NCD pair = %f\n", v);
    assert(v >= 0.0 && v <= 1.0);

    /* NCD matrix — exercises matrix internal allocs */
    const char* seq_strs[3] = {"abcdef", "abcdex", "different"};
    const unsigned char* seqs[3] = {(const unsigned char*)seq_strs[0],
                                    (const unsigned char*)seq_strs[1],
                                    (const unsigned char*)seq_strs[2]};
    size_t lengths[3] = {6, 6, 9};
    double matrix[9] = {0};
    rc = minxg_evolve_ncd_matrix_v1(seqs, lengths, 3, matrix);
    assert(rc == 0);

    printf("all paths exercised — ASan exit code will surface leaks.\n");
    return 0;
}
