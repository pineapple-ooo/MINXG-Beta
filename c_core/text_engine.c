/*
 * text_engine.c — Implementation: Boyer-Moore-Horspool, CSV stream parser,
 *                 glob matching, Unicode validation
 */

#include "text_engine.h"
#include <string.h>
#include <stdlib.h>
#include <limits.h>
#include <ctype.h>

/* ─── Boyer-Moore-Horspool (with 256-byte skip table) ─────────────────────── */

#define BM_SKIP_SIZE 256

static void bmh_build_skip(const uint8_t* needle, size_t n, size_t skip[BM_SKIP_SIZE]) {
    for (int i = 0; i < BM_SKIP_SIZE; i++) skip[i] = n;
    for (size_t j = 0; j < n - 1; j++) {
        skip[needle[j]] = n - 1 - j;
    }
}

int64_t minxg_memmem(const uint8_t* haystack, size_t hay_len,
                     const uint8_t* needle,  size_t ndl_len) {
    if (!haystack || !needle) return -1;
    if (ndl_len == 0) return 0;
    if (ndl_len > hay_len) return -1;

    size_t skip[BM_SKIP_SIZE];
    bmh_build_skip(needle, ndl_len, skip);

    size_t i = ndl_len - 1;
    while (i < hay_len) {
        size_t j = ndl_len - 1;
        size_t k = i;
        while (j > 0 && haystack[k] == needle[j]) { k--; j--; }
        if (j == 0 && haystack[k] == needle[0]) {
            return (int64_t)k;
        }
        i += skip[haystack[i]];
    }
    return -1;
}

int64_t minxg_memrmem(const uint8_t* haystack, size_t hay_len,
                      const uint8_t* needle,  size_t ndl_len) {
    if (!haystack || !needle) return -1;
    if (ndl_len == 0) return (int64_t)hay_len;
    if (ndl_len > hay_len) return -1;

    size_t skip[BM_SKIP_SIZE];
    bmh_build_skip(needle, ndl_len, skip);

    /* search backwards */
    size_t i = hay_len - 1;
    while (i >= ndl_len - 1) {
        size_t j = ndl_len - 1;
        size_t k = i;
        while (j > 0 && haystack[k] == needle[j]) { k--; j--; }
        if (j == 0 && haystack[k] == needle[0]) {
            return (int64_t)k;
        }
        size_t shift = skip[haystack[i]];
        i = (i >= shift) ? (i - shift) : 0;
    }
    return -1;
}

int minxg_memcnt(const uint8_t* haystack, size_t hay_len,
                 const uint8_t* needle,  size_t ndl_len) {
    if (!haystack || !needle || ndl_len == 0 || ndl_len > hay_len) return 0;

    size_t skip[BM_SKIP_SIZE];
    bmh_build_skip(needle, ndl_len, skip);

    int count = 0;
    size_t pos = ndl_len - 1;
    while (pos < hay_len) {
        size_t j = ndl_len - 1;
        size_t k = pos;
        while (j > 0 && haystack[k] == needle[j]) { k--; j--; }
        if (j == 0 && haystack[k] == needle[0]) {
            count++;
            pos = k + ndl_len + ndl_len - 1;
        } else {
            pos += skip[haystack[pos]];
        }
    }
    return count;
}

/* ─── String transforms (in-place) ───────────────────────────────────────── */

size_t minxg_str_lower(char* str, size_t len) {
    if (!str) return 0;
    for (size_t i = 0; i < len; i++) {
        str[i] = (char)tolower((unsigned char)str[i]);
    }
    return len;
}

size_t minxg_str_upper(char* str, size_t len) {
    if (!str) return 0;
    for (size_t i = 0; i < len; i++) {
        str[i] = (char)toupper((unsigned char)str[i]);
    }
    return len;
}

size_t minxg_str_trim(char* str, size_t len) {
    if (!str || len == 0) return 0;
    size_t start = 0;
    while (start < len && isspace((unsigned char)str[start])) start++;
    if (start == len) { str[0] = '\0'; return 0; }
    size_t end = len - 1;
    while (end > start && isspace((unsigned char)str[end])) end--;
    size_t new_len = end - start + 1;
    if (start > 0) memmove(str, str + start, new_len);
    str[new_len] = '\0';
    return new_len;
}

/* ─── CSV stream parser ──────────────────────────────────────────────────── */

minxg_csv_reader_t minxg_csv_open(const char* data, size_t len, char delim) {
    minxg_csv_reader_t r = {0};
    r.data = data;
    r.len  = len;
    r.delim = delim;
    r.row = 0;
    r.col = 0;
    return r;
}

int minxg_csv_next_cell(minxg_csv_reader_t* r, char* out_buf, size_t out_cap) {
    if (!r || !r->data || !out_buf || out_cap == 0) return -1;
    size_t p = r->pos;
    if (p >= r->len) return -1; /* EOF */

    /* skip \n at row start (but not at col > 0) */
    if (r->col == 0 && p < r->len && (r->data[p] == '\n' || r->data[p] == '\r')) {
        if (r->data[p] == '\r' && p + 1 < r->len && r->data[p+1] == '\n') p++;
        p++;
        r->row++;
        r->pos = p;
    }

    size_t start = p;
    while (p < r->len && r->data[p] != r->delim &&
           r->data[p] != '\n' && r->data[p] != '\r') {
        p++;
    }
    size_t cell_len = p - start;
    if (cell_len >= out_cap) return -1;
    memcpy(out_buf, r->data + start, cell_len);
    out_buf[cell_len] = '\0';

    if (p < r->len && r->data[p] == r->delim) {
        p++;  /* skip delimiter */
        r->col++;
    } else {
        /* newline */
        if (p < r->len && r->data[p] == '\r' && p + 1 < r->len && r->data[p+1] == '\n')
            p++;
        p++;
        r->row++;
        r->col = 0;
    }
    r->pos = p;
    return (int)cell_len;
}

void minxg_csv_count(const char* data, size_t len, char delim,
                     int* out_rows, int* out_cols) {
    if (!data) {
        if (out_rows) *out_rows = 0;
        if (out_cols) *out_cols = 0;
        return;
    }
    int cols = 1, rows = 0;
    size_t line_start = 0;
    for (size_t i = 0; i <= len; i++) {
        if (i == len || data[i] == '\n' || data[i] == '\r') {
            size_t line_len = i - line_start;
            if (line_len > 0) {
                if (rows == 0) {
                    cols = 1;
                    for (size_t j = line_start; j < i; j++) {
                        if (data[j] == delim) cols++;
                    }
                }
                rows++;
            }
            /* skip \r\n */
            if (i < len && data[i] == '\r' && i + 1 < len && data[i+1] == '\n') i++;
            line_start = i + 1;
        }
    }
    if (out_rows) *out_rows = rows;
    if (out_cols) *out_cols = cols;
}

/* ─── Glob matching (fnmatch-lite) ──────────────────────────────────────── */

static bool fnmatch_impl(const char* pat, const char* str, bool caseless) {
    while (*pat) {
        if (*pat == '*') {
            pat++;
            if (*pat == '\0') return true;
            while (*str) {
                if (fnmatch_impl(pat, str, caseless)) return true;
                str++;
            }
            return false;
        }
        if (*pat == '?') {
            if (*str == '\0') return false;
            pat++; str++;
            continue;
        }
        if (*str == '\0') return false;
        char pc = *pat, sc = *str;
        if (caseless) { pc = (char)tolower((unsigned char)pc); sc = (char)tolower((unsigned char)sc); }
        if (pc != sc) return false;
        pat++; str++;
    }
    return *str == '\0';
}

bool minxg_fnmatch(const char* pattern, const char* str) {
    return fnmatch_impl(pattern, str, false);
}

bool minxg_fnmatch_caseless(const char* pattern, const char* str) {
    return fnmatch_impl(pattern, str, true);
}

/* ─── Unicode helpers ──────────────────────────────────────────────────── */

int minxg_utf8_codepoint_count(const char* str, size_t len) {
    if (!str) return -1;
    int count = 0;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)str[i];
        if (c < 0x80) continue;
        if ((c & 0xE0) == 0xC0)      { i += 1; count++; continue; }
        if ((c & 0xF0) == 0xE0)      { i += 2; count++; continue; }
        if ((c & 0xF8) == 0xF0)      { i += 3; count++; continue; }
    }
    return count;
}

bool minxg_utf8_is_valid(const char* str, size_t len) {
    if (!str) return false;
    for (size_t i = 0; i < len; ) {
        unsigned char c = (unsigned char)str[i];
        if (c < 0x80) { i++; continue; }
        if ((c & 0xE0) == 0xC0) {
            if (i + 1 >= len || (str[i+1] & 0xC0) != 0x80) return false;
            i += 2;
        } else if ((c & 0xF0) == 0xE0) {
            if (i + 2 >= len || (str[i+1] & 0xC0) != 0x80 || (str[i+2] & 0xC0) != 0x80) return false;
            i += 3;
        } else if ((c & 0xF8) == 0xF0) {
            if (i + 3 >= len || (str[i+1] & 0xC0) != 0x80 || (str[i+2] & 0xC0) != 0x80 || (str[i+3] & 0xC0) != 0x80) return false;
            i += 4;
        } else {
            return false;
        }
    }
    return true;
}

int minxg_utf8_grapheme_count(const char* str, size_t len) {
    /* simple approximation: count code points (full segmentation needs ICU) */
    return minxg_utf8_codepoint_count(str, len);
}

/* ════════════════════════════════════════════════════════════════════════════
 * v0.0.2: String & math utility extensions
 * ════════════════════════════════════════════════════════════════════════════ */

#include <math.h>
#include <stdio.h>

/* ─── Slugify ────────────────────────────────────────────────────────────── */

size_t minxg_slugify(const char* input, size_t in_len, char* out_buf, size_t out_cap) {
    if (!input || !out_buf || out_cap == 0) return 0;
    size_t w = 0;
    int last_was_dash = 0;
    for (size_t i = 0; i < in_len && w < out_cap - 1; i++) {
        unsigned char c = (unsigned char)input[i];
        if (isalnum(c)) {
            out_buf[w++] = (char)tolower(c);
            last_was_dash = 0;
        } else if ((c == ' ' || c == '-' || c == '_') && !last_was_dash && w > 0) {
            out_buf[w++] = '-';
            last_was_dash = 1;
        }
    }
    /* trim trailing dash */
    while (w > 0 && out_buf[w-1] == '-') w--;
    out_buf[w] = '\0';
    return w;
}

/* ─── Truncate ───────────────────────────────────────────────────────────── */

size_t minxg_truncate(const char* input, size_t in_len, size_t max_len,
                      const char* suffix, size_t suf_len,
                      char* out_buf, size_t out_cap) {
    if (!input || !out_buf || out_cap == 0) return 0;
    if (in_len <= max_len) {
        size_t n = in_len < out_cap - 1 ? in_len : out_cap - 1;
        memcpy(out_buf, input, n);
        out_buf[n] = '\0';
        return n;
    }
    size_t avail = (max_len > suf_len) ? (max_len - suf_len) : 0;
    if (avail > out_cap - 1) avail = out_cap - 1 - suf_len;
    if (avail > 0) {
        memcpy(out_buf, input, avail);
        out_buf += avail;
    }
    if (suf_len > 0 && (avail + suf_len) < out_cap - 1) {
        memcpy(out_buf, suffix, suf_len);
        out_buf[suf_len] = '\0';
        return avail + suf_len;
    }
    out_buf[0] = '\0';
    return 0;
}

/* ─── Word Frequency Hash ────────────────────────────────────────────────── */

#define WF_HASH_SIZE 4096

typedef struct {
    char* word;
    int   count;
    int   occupied;
} wf_entry_t;

static unsigned int wf_hash(const char* s, size_t len) {
    unsigned int h = 5381;
    for (size_t i = 0; i < len; i++) h = ((h << 5) + h) + (unsigned char)s[i];
    return h % WF_HASH_SIZE;
}

size_t minxg_word_freq_hash(const char* input, size_t in_len,
                            int top_n, char* out_buf, size_t out_cap) {
    if (!input || !out_buf || out_cap < 4 || top_n <= 0) return 0;

    wf_entry_t table[WF_HASH_SIZE];
    memset(table, 0, sizeof(table));

    /* tokenize and count */
    const char* p = input;
    const char* end = input + in_len;
    while (p < end) {
        /* skip non-alnum */
        while (p < end && !isalnum((unsigned char)*p)) p++;
        if (p >= end) break;
        const char* word_start = p;
        while (p < end && isalnum((unsigned char)*p)) p++;
        size_t wlen = (size_t)(p - word_start);
        if (wlen == 0 || wlen > 127) continue;

        /* lowercase copy */
        char lc[128];
        for (size_t i = 0; i < wlen; i++) lc[i] = (char)tolower((unsigned char)word_start[i]);
        lc[wlen] = '\0';

        unsigned int h = wf_hash(lc, wlen);
        int found = 0;
        for (int probe = 0; probe < 32; probe++) {
            unsigned int idx = (h + (unsigned int)probe) % WF_HASH_SIZE;
            if (!table[idx].occupied) {
                table[idx].word = strdup(lc);
                table[idx].count = 1;
                table[idx].occupied = 1;
                found = 1;
                break;
            } else if (table[idx].word && strcmp(table[idx].word, lc) == 0) {
                table[idx].count++;
                found = 1;
                break;
            }
        }
        (void)found;
    }

    /* collect non-empty entries */
    typedef struct { const char* word; int count; } freq_t;
    freq_t freqs[WF_HASH_SIZE];
    int nf = 0;
    for (int i = 0; i < WF_HASH_SIZE; i++) {
        if (table[i].occupied && table[i].word) {
            freqs[nf].word = table[i].word;
            freqs[nf].count = table[i].count;
            nf++;
        }
    }

    /* bubble sort by count desc (simple, n<=4096 is fine) */
    for (int i = 0; i < nf - 1; i++)
        for (int j = i + 1; j < nf; j++)
            if (freqs[j].count > freqs[i].count) {
                freq_t tmp = freqs[i]; freqs[i] = freqs[j]; freqs[j] = tmp;
            }

    /* format output */
    size_t w = 0;
    int limit = (top_n < nf) ? top_n : nf;
    for (int i = 0; i < limit; i++) {
        int n = snprintf(out_buf + w, out_cap - w, "%s%s:%d",
                         i > 0 ? "," : "", freqs[i].word, freqs[i].count);
        if (n < 0 || (size_t)n >= out_cap - w) break;
        w += (size_t)n;
    }

    /* free strdup'd words */
    for (int i = 0; i < WF_HASH_SIZE; i++)
        if (table[i].occupied && table[i].word) free(table[i].word);

    return w;
}

/* ─── Extract URLs ───────────────────────────────────────────────────────── */

static int is_url_char(unsigned char c) {
    return isalnum(c) || c == '.' || c == '/' || c == ':' || c == '-'
        || c == '_' || c == '?' || c == '&' || c == '=' || c == '%'
        || c == '#' || c == '@' || c == '+' || c == '~';
}

int minxg_extract_urls(const char* input, size_t in_len,
                       char* out_buf, size_t out_cap, int max_urls) {
    if (!input || !out_buf || out_cap == 0) return 0;
    size_t w = 0;
    int count = 0;
    const char* p = input;
    const char* end = input + in_len;

    while (p < end && count < max_urls) {
        /* look for "http" */
        const char* proto = NULL;
        for (; p < end - 4; p++) {
            if ((p[0]=='h'||p[0]=='H') && (p[1]=='t'||p[1]=='T') &&
                (p[2]=='t'||p[2]=='T') && (p[3]=='p'||p[3]=='P')) {
                proto = p;
                break;
            }
        }
        if (!proto || proto >= end - 7) break;
        p = proto + 4;
        if (p < end && (*p == 's' || *p == 'S')) { p++; }
        if (p + 3 >= end || p[0] != ':' || p[1] != '/' || p[2] != '/') continue;
        p += 3;

        const char* url_start = proto;
        while (p < end && is_url_char((unsigned char)*p)) p++;
        size_t url_len = (size_t)(p - url_start);
        if (url_len > out_cap - w - 2) break;

        memcpy(out_buf + w, url_start, url_len);
        w += url_len;
        out_buf[w++] = '\0';
        count++;
    }
    out_buf[w] = '\0';
    return count;
}

/* ─── Extract Emails ─────────────────────────────────────────────────────── */

static int is_email_char(unsigned char c) {
    return isalnum(c) || c == '.' || c == '_' || c == '%' || c == '+'
        || c == '-' || c == '@';
}

int minxg_extract_emails(const char* input, size_t in_len,
                         char* out_buf, size_t out_cap, int max_emails) {
    if (!input || !out_buf || out_cap == 0) return 0;
    size_t w = 0;
    int count = 0;
    const char* p = input;
    const char* end = input + in_len;

    while (p < end && count < max_emails) {
        /* find '@' */
        const char* at = NULL;
        for (; p < end; p++) { if (*p == '@') { at = p; p++; break; } }
        if (!at) break;

        /* backtrack to find start of local part */
        const char* start = at;
        while (start > input && is_email_char((unsigned char)*(start-1))
               && *(start-1) != '@') start--;

        /* forward to end of domain */
        const char* dom_end = at + 1;
        while (dom_end < end && (isalnum((unsigned char)*dom_end)
               || *dom_end == '.' || *dom_end == '-')) dom_end++;

        /* must have at least 1 char before @ and a dot after */
        if (start >= at || dom_end <= at + 1) continue;
        const char* dot = strchr(at + 1, '.');
        if (!dot || dot >= dom_end) continue;

        size_t em_len = (size_t)(dom_end - start);
        if (em_len > out_cap - w - 2) break;
        memcpy(out_buf + w, start, em_len);
        w += em_len;
        out_buf[w++] = '\0';
        count++;
    }
    return count;
}

/* ─── Extract Hashtags ───────────────────────────────────────────────────── */

int minxg_extract_hashtags(const char* input, size_t in_len,
                           char* out_buf, size_t out_cap, int max_tags) {
    if (!input || !out_buf || out_cap == 0) return 0;
    size_t w = 0;
    int count = 0;
    const char* p = input;
    const char* end = input + in_len;
    const char* start = NULL;

    for (; p < end; p++) {
        if (*p == '#') {
            start = p;
            p++;
            while (p < end && (isalnum((unsigned char)*p) || *p == '_')) p++;
            size_t tag_len = (size_t)(p - start);
            p--;  /* outer loop will increment */
            if (tag_len > 1 && tag_len < out_cap - w - 2 && count < max_tags) {
                memcpy(out_buf + w, start, tag_len);
                w += tag_len;
                out_buf[w++] = '\0';
                count++;
            }
        }
    }
    return count;
}

/* ─── Normalize Whitespace ────────────────────────────────────────────────── */

size_t minxg_normalize_ws(const char* input, size_t in_len,
                          int line_ending, char* out_buf, size_t out_cap) {
    if (!input || !out_buf || out_cap == 0) return 0;
    const char* p = input;
    const char* end = input + in_len;
    size_t w = 0;
    int in_space = 1;  /* start in-space to trim leading */

    while (p < end && w < out_cap - 1) {
        unsigned char c = (unsigned char)*p;
        if (c == '\r' || c == '\n') {
            if (line_ending == 1 && c == '\r' && p+1 < end && *(p+1) == '\n') p++;
            else if (line_ending == 0 && c == '\r' && p+1 < end && *(p+1) == '\n') p++;
            if (!in_space) out_buf[w++] = '\n';
            p++;
            in_space = 1;
            continue;
        }
        if (c == ' ' || c == '\t') {
            if (!in_space && w > 0) out_buf[w++] = ' ';
            p++;
            in_space = 1;
            continue;
        }
        out_buf[w++] = (char)c;
        in_space = 0;
        p++;
    }
    /* trim trailing space */
    while (w > 0 && (out_buf[w-1] == ' ' || out_buf[w-1] == '\n')) w--;
    out_buf[w] = '\0';
    return w;
}

/* ─── Base Convert ───────────────────────────────────────────────────────── */

static const char BASE36_DIGITS[] = "0123456789abcdefghijklmnopqrstuvwxyz";

int minxg_base_convert(const char* number, int base_fr, int base_to,
                       char* out_buf, size_t out_cap) {
    if (!number || !out_buf || out_cap < 2) return -1;
    if (base_fr < 2 || base_fr > 36 || base_to < 2 || base_to > 36) return -1;

    /* parse from base_fr */
    int64_t n = 0;
    int neg = 0;
    const char* p = number;
    if (*p == '-') { neg = 1; p++; }

    for (; *p; p++) {
        unsigned char c = (unsigned char)*p;
        int d;
        if (c >= '0' && c <= '9') d = c - '0';
        else if (c >= 'a' && c <= 'z') d = c - 'a' + 10;
        else if (c >= 'A' && c <= 'Z') d = c - 'A' + 10;
        else return -1;
        if (d >= base_fr) return -1;
        n = n * (int64_t)base_fr + d;
    }

    /* convert to base_to */
    if (n == 0) { out_buf[0] = '0'; out_buf[1] = '\0'; return 1; }
    char tmp[128];
    int pos = 0;
    while (n > 0 && pos < 127) {
        tmp[pos++] = BASE36_DIGITS[n % (unsigned)base_to];
        n /= (int64_t)base_to;
    }
    int w = 0;
    if (neg && w < (int)(out_cap - 1)) out_buf[w++] = '-';
    for (int i = pos - 1; i >= 0 && w < (int)(out_cap - 1); i--)
        out_buf[w++] = tmp[i];
    out_buf[w] = '\0';
    return w;
}

/* ─── Statistics ──────────────────────────────────────────────────────────── */

static int cmp_double(const void* a, const void* b) {
    double da = *(const double*)a, db = *(const double*)b;
    return (da > db) - (da < db);
}

int minxg_statistics(const double* values, size_t count,
                     double* out_mean, double* out_std,
                     double* out_median, double* out_min,
                     double* out_max, double* out_sum) {
    if (!values || count == 0) return -1;
    double sum = 0.0, m = 0.0, min_v = values[0], max_v = values[0];

    for (size_t i = 0; i < count; i++) {
        double v = values[i];
        sum += v;
        if (v < min_v) min_v = v;
        if (v > max_v) max_v = v;
    }
    double mean = sum / (double)count;

    /* std */
    double sum_sq = 0.0;
    for (size_t i = 0; i < count; i++) {
        double d = values[i] - mean;
        sum_sq += d * d;
    }
    double std = sqrt(sum_sq / (double)count);

    /* median: sort a copy */
    double* sorted = (double*)malloc(count * sizeof(double));
    if (sorted) {
        memcpy(sorted, values, count * sizeof(double));
        qsort(sorted, count, sizeof(double), cmp_double);
        if (count % 2 == 1)
            m = sorted[count / 2];
        else
            m = (sorted[count / 2 - 1] + sorted[count / 2]) / 2.0;
        free(sorted);
    }

    if (out_mean)   *out_mean = mean;
    if (out_std)    *out_std = std;
    if (out_median) *out_median = m;
    if (out_min)    *out_min = min_v;
    if (out_max)    *out_max = max_v;
    if (out_sum)    *out_sum = sum;
    return 0;
}