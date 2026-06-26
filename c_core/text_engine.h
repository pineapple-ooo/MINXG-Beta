/*
 * text_engine.h — C text processing: SIMD-aware substring search,
 *                 fast CSV/TSV parser, regex-lite glob, Unicode normalization
 *
 * All functions zero-alloc — caller provides buffers.
 * Pure C11, no dependencies beyond libc.
 */

#ifndef MINXG_TEXT_ENGINE_H
#define MINXG_TEXT_ENGINE_H

#include "minxg_arch.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ─── SIMD-aware memmem (Boyer-Moore-Horspool with SSE2/NEON detection) ─── */
/*
 * Returns offset of first match, or -1 if not found.
 * Uses hardware detection at runtime to choose the best codepath.
 */
int64_t minxg_memmem(const uint8_t* haystack, size_t hay_len,
                     const uint8_t* needle,  size_t ndl_len);
int64_t minxg_memrmem(const uint8_t* haystack, size_t hay_len,
                      const uint8_t* needle,  size_t ndl_len);
int     minxg_memcnt(const uint8_t* haystack, size_t hay_len,
                     const uint8_t* needle,  size_t ndl_len);

/* ─── String transforms (in-place, zero-alloc) ──────────────────────────── */
size_t minxg_str_lower(char* str, size_t len);
size_t minxg_str_upper(char* str, size_t len);
size_t minxg_str_trim(char* str, size_t len);  /* returns new len */

/* ─── Fast CSV parser — streaming, allocates nothing ────────────────────── */
typedef struct {
    const char* data;
    size_t      len;
    size_t      pos;
    int         row;
    int         col;
    char        delim;
} minxg_csv_reader_t;

minxg_csv_reader_t minxg_csv_open(const char* data, size_t len, char delim);
/*
 * Returns length of cell written to out_buf (0 = empty cell, -1 = EOF).
 * out_buf must be at least out_cap bytes.
 */
int minxg_csv_next_cell(minxg_csv_reader_t* r, char* out_buf, size_t out_cap);

/*
 * minxg_csv_count — quick row/col count without parsing content.
 * out_rows/out_cols may be NULL.
 */
void minxg_csv_count(const char* data, size_t len, char delim,
                     int* out_rows, int* out_cols);

/* ─── Glob matching (fnmatch-lite, zero-alloc) ─────────────────────────── */
bool minxg_fnmatch(const char* pattern, const char* str);
bool minxg_fnmatch_caseless(const char* pattern, const char* str);

/* ─── Unicode helpers ──────────────────────────────────────────────────── */
int  minxg_utf8_codepoint_count(const char* str, size_t len);
bool minxg_utf8_is_valid(const char* str, size_t len);
int  minxg_utf8_grapheme_count(const char* str, size_t len);

/* ─── String utilities (new in v0.0.2) ──────────────────────────────────── */

/* slugify: convert to lowercase, strip non-word chars, collapse '-' and spaces */
size_t minxg_slugify(const char* input, size_t in_len, char* out_buf, size_t out_cap);

/* truncate: cut to max_len, append suffix if truncated. Returns final len. */
size_t minxg_truncate(const char* input, size_t in_len, size_t max_len,
                      const char* suffix, size_t suf_len,
                      char* out_buf, size_t out_cap);

/* word_frequency_hash: count word frequencies, return key:count pairs as CSV
 * out_buf receives "word1:N1,word2:N2,..." sorted by count desc.
 * Returns total bytes written (excluding null) or 0 on error. */
size_t minxg_word_freq_hash(const char* input, size_t in_len,
                            int top_n, char* out_buf, size_t out_cap);

/* extract_urls: find all http/https URLs, return count. out_buf receives
 * null-separated list. Max urls capped at max_urls. */
int minxg_extract_urls(const char* input, size_t in_len,
                       char* out_buf, size_t out_cap, int max_urls);

/* extract_emails: find all email addresses, return count. */
int minxg_extract_emails(const char* input, size_t in_len,
                         char* out_buf, size_t out_cap, int max_emails);

/* extract_hashtags: find all #tags, return count. */
int minxg_extract_hashtags(const char* input, size_t in_len,
                           char* out_buf, size_t out_cap, int max_tags);

/* normalize_whitespace: trim, collapse multiple spaces, unify line endings.
 * line_ending: 0='\n', 1='\r\n', 2='\r'. Returns final length. */
size_t minxg_normalize_ws(const char* input, size_t in_len,
                          int line_ending, char* out_buf, size_t out_cap);

/* ─── Math utilities ────────────────────────────────────────────────────── */

/* base_convert: convert number string from base_fr to base_to.
 * Supports bases 2-36. out_buf receives the result. Returns length. */
int minxg_base_convert(const char* number, int base_fr, int base_to,
                       char* out_buf, size_t out_cap);

/* statistics: compute count, mean, std, median, min, max, sum from flat
 * array of doubles. Returns 0 on success, -1 on error. */
int minxg_statistics(const double* values, size_t count,
                     double* out_mean, double* out_std,
                     double* out_median, double* out_min,
                     double* out_max, double* out_sum);

#ifdef __cplusplus
}
#endif

#endif /* MINXG_TEXT_ENGINE_H */