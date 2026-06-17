/* ═══════════════════════════════════════════════════════════════════════
 * text_engine.c — MINXG C core: brute-force search, text utils
 * All functions match text_engine.h + minxg_arch.h signatures
 * ═══════════════════════════════════════════════════════════════════════ */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <ctype.h>
#include <math.h>
#include <zlib.h>
#include "text_engine.h"
#include "minxg_arch.h"

#ifndef MIN
#define MIN(a,b) ((size_t)(a) < (size_t)(b) ? (size_t)(a) : (size_t)(b))
#endif
#ifndef MAX
#define MAX(a,b) ((size_t)(a) > (size_t)(b) ? (size_t)(a) : (size_t)(b))
#endif

/* ════════════════════════════════════════════════════════════════════════
 * STRING SEARCH — brute force (guaranteed correct, no optimizer surprises)
 * ════════════════════════════════════════════════════════════════════════ */

int64_t minxg_bmh_search(const uint8_t* h, size_t hl, const uint8_t* n, size_t nl) {
    size_t i, j;
    if (!h || !n || hl == 0 || nl == 0 || nl > hl) return -1;
    for (i = 0; i <= hl - nl; i++) {
        for (j = 0; j < nl; j++) {
            if (h[i + j] != n[j]) break;
        }
        if (j == nl) return (int64_t)i;
    }
    return -1;
}

int64_t minxg_bmh_count(const uint8_t* h, size_t hl, const uint8_t* n, size_t nl) {
    size_t i, j;
    int64_t count = 0;
    if (!h || !n || hl == 0 || nl == 0 || nl > hl) return 0;
    for (i = 0; i <= hl - nl; i++) {
        for (j = 0; j < nl; j++) {
            if (h[i + j] != n[j]) break;
        }
        if (j == nl) count++;
    }
    return count;
}

int64_t minxg_memmem(const uint8_t* h, size_t hl, const uint8_t* n, size_t nl) {
    return minxg_bmh_search(h, hl, n, nl);
}

int64_t minxg_memrmem(const uint8_t* h, size_t hl, const uint8_t* n, size_t nl) {
    size_t i, j;
    if (!h || !n || hl == 0 || nl == 0 || nl > hl) return -1;
    for (i = hl - nl + 1; i > 0; i--) {
        for (j = 0; j < nl; j++) {
            if (h[i - 1 + j] != n[j]) break;
        }
        if (j == nl) return (int64_t)(i - 1);
    }
    return -1;
}

int minxg_memcnt(const uint8_t* h, size_t hl, const uint8_t* n, size_t nl) {
    return (int)minxg_bmh_count(h, hl, n, nl);
}

/* ════════════════════════════════════════════════════════════════════════
 * STRING TRANSFORMS
 * ════════════════════════════════════════════════════════════════════════ */

size_t minxg_str_lower(char* str, size_t len) {
    size_t i;
    if (!str) return 0;
    for (i = 0; i < len; i++) str[i] = (char)tolower((unsigned char)str[i]);
    return len;
}

size_t minxg_str_upper(char* str, size_t len) {
    size_t i;
    if (!str) return 0;
    for (i = 0; i < len; i++) str[i] = (char)toupper((unsigned char)str[i]);
    return len;
}

size_t minxg_str_trim(char* str, size_t len) {
    size_t i, start, end;
    if (!str || len == 0) return 0;
    start = 0;
    while (start < len && isspace((unsigned char)str[start])) start++;
    end = len;
    while (end > start && isspace((unsigned char)str[end - 1])) end--;
    if (start > 0) {
        for (i = 0; i < end - start; i++) str[i] = str[start + i];
    }
    return end - start;
}

size_t minxg_slugify(const char* in, size_t in_len, char* out, size_t out_cap) {
    size_t wi = 0, i;
    int last_dash = 0;
    if (!in || !out || out_cap == 0) return 0;
    for (i = 0; i < in_len; i++) {
        unsigned char c = (unsigned char)in[i];
        if (isalnum(c)) {
            if (wi + 1 < out_cap) out[wi++] = (char)tolower(c);
            last_dash = 0;
        } else if (isspace(c) || c == '-' || c == '_' || c == '.') {
            if (!last_dash && wi > 0 && wi + 1 < out_cap) {
                out[wi++] = '-';
                last_dash = 1;
            }
        }
    }
    while (wi > 0 && out[wi - 1] == '-') wi--;
    out[wi] = '\0';
    return wi;
}

size_t minxg_truncate(const char* in, size_t in_len, size_t max_len,
                      const char* suffix, size_t suffix_len,
                      char* out, size_t out_cap) {
    size_t suf = suffix ? suffix_len : 0;
    size_t vis = (suf >= max_len) ? 0 : max_len - suf;
    if (vis > in_len) vis = in_len;
    if (vis + suf > out_cap) vis = (out_cap > suf) ? out_cap - suf : 0;
    if (vis > 0) memcpy(out, in, vis);
    if (suffix && suf > 0 && vis + suf <= out_cap) memcpy(out + vis, suffix, suf);
    out[vis + (suffix ? MIN(suf, out_cap - vis) : 0)] = '\0';
    return vis + (suffix ? MIN(suf, out_cap - vis) : 0) + 1;
}

size_t minxg_normalize_ws(const char* in, size_t in_len,
                          int line_ending, char* out, size_t out_cap) {
    size_t wi = 0, i;
    int was_ws = 0;
    (void)line_ending;
    if (!in || !out || out_cap == 0) return 0;
    for (i = 0; i < in_len; i++) {
        unsigned char c = (unsigned char)in[i];
        if (isspace(c)) {
            if (!was_ws && wi > 0 && wi + 1 < out_cap) {
                out[wi++] = ' ';
                was_ws = 1;
            }
        } else {
            if (wi < out_cap - 1) out[wi++] = (char)c;
            was_ws = 0;
        }
    }
    while (wi > 0 && out[wi - 1] == ' ') wi--;
    out[wi] = '\0';
    return wi + 1;
}

/* ════════════════════════════════════════════════════════════════════════
 * TEXT EXTRACTORS
 * ════════════════════════════════════════════════════════════════════════ */

size_t minxg_word_freq_hash(const char* text, size_t text_len,
                            int top_n, char* out_buf, size_t out_cap) {
    typedef struct { uint64_t h; int cnt; char w[64]; } E;
    E e[512];
    int ec = 0;
    int ii, jj;
    size_t kk;
    memset(e, 0, sizeof(e));
    (void)text_len;

    /* Parse words with pointer arithmetic */
    const char* p = text;
    while (*p) {
        while (*p && isspace((unsigned char)*p)) p++;
        if (!*p) break;
        {
            const char* ws = p;
            while (*p && !isspace((unsigned char)*p)) p++;
            {
                size_t wl = (size_t)(p - ws);
                if (wl > 0 && wl < 64) {
                    uint64_t h2 = 5381;
                    for (kk = 0; kk < wl; kk++) {
                        h2 = h2 * 33 ^ (unsigned char)ws[kk];
                    }
                    {
                        int fi = -1;
                        for (kk = 0; kk < (size_t)ec; kk++) {
                            if (e[kk].h == h2) { fi = (int)kk; break; }
                        }
                        if (fi >= 0) {
                            e[fi].cnt++;
                        } else if (ec < 512) {
                            E* ne = &e[ec++];
                            ne->h = h2;
                            ne->cnt = 1;
                            for (kk = 0; kk < wl; kk++) ne->w[kk] = ws[kk];
                            ne->w[wl] = '\0';
                        }
                    }
                }
            }
        }
    }

    /* Bubble sort by count descending */
    for (ii = 0; ii < ec - 1; ii++) {
        for (jj = ii + 1; jj < ec; jj++) {
            if (e[jj].cnt > e[ii].cnt) {
                E tmp = e[ii]; e[ii] = e[jj]; e[jj] = tmp;
            }
        }
    }

    {
        int nn = (top_n <= 0) ? ec : (top_n < ec ? top_n : ec);
        size_t wi = 0;
        for (ii = 0; ii < nn; ii++) {
            char buf[128];
            int bl = snprintf(buf, sizeof(buf), "%s:%d", e[ii].w, e[ii].cnt);
            if (bl > 0 && (size_t)bl < out_cap - wi) {
                for (kk = 0; kk < (size_t)bl; kk++) out_buf[wi++] = buf[kk];
                out_buf[wi++] = '\0';
            }
        }
        out_buf[wi] = '\0';
        return (size_t)nn;
    }
}

/* ─── Extract URLs ──────────────────────────────────────────────────────── */

static int is_url_char(int c) {
    return isalnum(c) || c=='/' || c=='?' || c=='#' || c=='@' ||
           c=='&' || c=='=' || c=='+' || c=='$' || c==',' ||
           c=='-' || c=='_' || c=='.' || c=='~' || c==':' ;
}

int minxg_extract_urls(const char* input, size_t in_len,
                       char* out_buf, size_t out_cap, int max_urls) {
    size_t w = 0, pos = 0;
    int count = 0;
    if (!input || !out_buf || out_cap == 0) return 0;

    while (count < max_urls && pos < in_len) {
        while (pos < in_len && input[pos] != 'h' && input[pos] != 'H') pos++;
        if (pos >= in_len) break;

        if (pos + 4 <= in_len &&
            (input[pos+1]=='t'||input[pos+1]=='T') &&
            (input[pos+2]=='t'||input[pos+2]=='T') &&
            (input[pos+3]=='p'||input[pos+3]=='P')) {
            int is_https = (pos + 5 <= in_len && (input[pos+4]=='s'||input[pos+4]=='S'));
            size_t skip = is_https ? 5 : 4;
            if (pos + skip + 3 <= in_len &&
                input[pos+skip]==':' && input[pos+skip+1]=='/' && input[pos+skip+2]=='/') {
                /* url_start = start of scheme (include http:// or https://) */
                size_t url_start = pos;
                /* url_end scans including the :// part */
                size_t url_end = url_start;
                while (url_end < in_len && is_url_char((unsigned char)input[url_end])) url_end++;
                if (url_end > url_start) {
                    size_t len = url_end - url_start;
                    if (w + len + 1 <= out_cap) {
                        size_t kk;
                        for (kk = 0; kk < len; kk++) out_buf[w++] = input[url_start + kk];
                        out_buf[w++] = '\0';
                        count++;
                    }
                    pos = url_end;
                    continue;
                }
            }
        }
        pos++;
    }
    out_buf[w] = '\0';
    return count;
}

/* ─── Extract Emails ────────────────────────────────────────────────────── */

static int is_email_char(int c) {
    return isalnum(c) || c=='.' || c=='_' || c=='%' || c=='+' || c=='-';
}

int minxg_extract_emails(const char* input, size_t in_len,
                         char* out_buf, size_t out_cap, int max_emails) {
    size_t w = 0, pos = 0;
    int count = 0;
    if (!input || !out_buf || out_cap == 0) return 0;

    while (count < max_emails && pos < in_len) {
        while (pos < in_len && input[pos] != '@') pos++;
        if (pos >= in_len) break;
        {
            const char* at = input + pos;
            const char* local_start = at;
            while (local_start > input && is_email_char((unsigned char)*(local_start - 1)))
                local_start--;
            const char* dom_end = at + 1;
            while (dom_end < input + in_len && is_email_char((unsigned char)*dom_end))
                dom_end++;
            size_t llen = (size_t)(at - local_start);
            size_t dlen = (size_t)(dom_end - (at + 1));
            if (llen > 0 && dlen > 0 && w + llen + dlen + 2 <= out_cap) {
                size_t kk;
                for (kk = 0; kk < llen; kk++) out_buf[w++] = local_start[kk];
                out_buf[w++] = '@';
                for (kk = 0; kk < dlen; kk++) out_buf[w++] = at[1 + kk];
                out_buf[w++] = '\0';
                count++;
            }
            pos = (size_t)(dom_end - input);
        }
    }
    out_buf[w] = '\0';
    return count;
}

/* ─── Extract Hashtags ─────────────────────────────────────────────────── */

static int is_tag_char(int c) {
    return isalpha(c) || (c & 0x80);
}

int minxg_extract_hashtags(const char* input, size_t in_len,
                           char* out_buf, size_t out_cap, int max_tags) {
    size_t w = 0, pos = 0;
    int count = 0;
    if (!input || !out_buf || out_cap == 0) return 0;

    while (count < max_tags && pos < in_len) {
        while (pos < in_len && input[pos] != '#') pos++;
        if (pos >= in_len) break;
        {
            size_t tag_start = pos;
            size_t tag_end = pos + 1;
            while (tag_end < in_len && is_tag_char((unsigned char)input[tag_end])) tag_end++;
            if (tag_end > tag_start + 1) {
                size_t len = tag_end - tag_start;
                if (w + len + 1 <= out_cap) {
                    size_t kk;
                    for (kk = 0; kk < len; kk++) out_buf[w++] = input[tag_start + kk];
                    out_buf[w++] = '\0';
                    count++;
                }
                pos = tag_end;
                continue;
            }
        }
        pos++;
    }
    out_buf[w] = '\0';
    return count;
}

/* ─── Base convert ─────────────────────────────────────────────────────── */

int minxg_base_convert(const char* num, int from, int to, char* out, size_t out_cap) {
    unsigned long val = 0;
    const char* p;
    if (!num || !out || from < 2 || from > 36 || to < 2 || to > 36 || out_cap == 0)
        return -1;
    p = num;
    while (*p) {
        int d; char c = *p;
        if (c >= '0' && c <= '9') d = c - '0';
        else if (c >= 'a' && c <= 'z') d = c - 'a' + 10;
        else if (c >= 'A' && c <= 'Z') d = c - 'A' + 10;
        else return -1;
        if (d >= from) return -1;
        val = val * (unsigned long)from + (unsigned long)d;
        p++;
    }
    if (val == 0) { out[0] = '0'; out[1] = '\0'; return 1; }
    {
        char rev[128];
        int ti = 0;
        while (val > 0) {
            int d = (int)(val % (unsigned long)to);
            rev[ti++] = (d < 10) ? ('0' + d) : ('a' + d - 10);
            val /= (unsigned long)to;
        }
        if (ti >= (int)out_cap) return -1;
        {
            int kk;
            for (kk = 0; kk < ti; kk++) out[kk] = rev[ti - 1 - kk];
        }
        out[ti] = '\0';
        return ti;
    }
}

/* ─── Statistics ──────────────────────────────────────────────────────── */

int minxg_statistics(const double* values, size_t count,
                     double* out_mean, double* out_std,
                     double* out_median, double* out_min,
                     double* out_max, double* out_sum) {
    size_t i;
    double sum = 0, min_v = 0, max_v = 0;
    if (!values || count == 0) return -1;
    min_v = values[0]; max_v = values[0];
    for (i = 0; i < count; i++) {
        sum += values[i];
        if (values[i] < min_v) min_v = values[i];
        if (values[i] > max_v) max_v = values[i];
    }
    {
        double mean = sum / (double)count;
        double var = 0;
        for (i = 0; i < count; i++) {
            double d = values[i] - mean;
            var += d * d;
        }
        {
            double* s = (double*)malloc(count * sizeof(double));
            if (!s) return -1;
            for (i = 0; i < count; i++) s[i] = values[i];
            /* Insertion sort */
            {
                size_t ii, jj;
                for (ii = 1; ii < count; ii++) {
                    double key = s[ii];
                    jj = ii;
                    while (jj > 0 && s[jj-1] > key) {
                        s[jj] = s[jj-1];
                        jj--;
                    }
                    s[jj] = key;
                }
            }
            {
                double med = (count % 2 == 0)
                    ? (s[count/2-1] + s[count/2]) * 0.5
                    : s[count/2];
                free(s);
                if (out_mean) *out_mean = mean;
                if (out_std) *out_std = sqrt(var / (double)count);
                if (out_median) *out_median = med;
                if (out_min) *out_min = min_v;
                if (out_max) *out_max = max_v;
                if (out_sum) *out_sum = sum;
                return 0;
            }
        }
    }
}

/* ─── NCD ─────────────────────────────────────────────────────────────── */

double minxg_ncd(const uint8_t* a, size_t al, const uint8_t* b, size_t bl,
                 uint8_t* abuf, size_t abuf_cap, uint8_t* bbuf, size_t bbuf_cap) {
    uLongf cal, cbl;
    uint8_t* cab;
    double ncd = -1.0;
    if (!a || !b || al == 0 || bl == 0) return -1.0;
    cal = compressBound(al);
    cbl = compressBound(bl);
    if ((size_t)cal > abuf_cap || (size_t)cbl > bbuf_cap) return -1.0;
    if (compress(abuf, &cal, a, al) != Z_OK) return -1.0;
    if (compress(bbuf, &cbl, b, bl) != Z_OK) return -1.0;
    cab = (uint8_t*)malloc((size_t)(cal + cbl));
    if (cab) {
        memcpy(cab, abuf, (size_t)cal);
        memcpy(cab + (size_t)cal, bbuf, (size_t)cbl);
        {
            uLongf ccab = (uLongf)(cal + cbl + 256);
            uint8_t* ccabuf = (uint8_t*)malloc(ccab);
            if (ccabuf) {
                if (compress(ccabuf, &ccab, cab, (uLongf)(cal + cbl)) == Z_OK) {
                    double cx = (double)cal;
                    double cy = (double)cbl;
                    double cxy = (double)ccab;
                    if (cx + cy > 0) {
                        ncd = (cxy - MIN(cx, cy)) / MAX(cx, cy);
                    }
                }
                free(ccabuf);
            }
        }
        free(cab);
    }
    return ncd;
}

/* ─── fnmatch ──────────────────────────────────────────────────────────── */

bool minxg_fnmatch(const char* pat, const char* str) {
    const char *p = pat, *s = str, *mp = NULL, *ms = NULL;
    if (!pat || !str) return false;
    while (*s) {
        if (*p == '*') { mp = p; ms = s; do { p++; } while (*p == '*'); continue; }
        if (*p == '?' || *p == *s) { p++; s++; }
        else if (mp) { p = mp + 1; s = ms + 1; ms++; }
        else return false;
    }
    while (*p == '*') p++;
    return (*p == '\0');
}

bool minxg_fnmatch_caseless(const char* pat, const char* str) {
    const char *p = pat, *s = str, *mp = NULL, *ms = NULL;
    if (!pat || !str) return false;
    while (*s) {
        if (*p == '*') { mp = p; ms = s; do { p++; } while (*p == '*'); continue; }
        if (*p == '?' || tolower((unsigned char)*p) == tolower((unsigned char)*s)) { p++; s++; }
        else if (mp) { p = mp + 1; s = ms + 1; ms++; }
        else return false;
    }
    while (*p == '*') p++;
    return (*p == '\0');
}

/* ─── UTF-8 helpers ───────────────────────────────────────────────────── */

int minxg_utf8_codepoint_count(const char* str, size_t len) {
    int cnt = 0;
    size_t i;
    if (!str) return 0;
    for (i = 0; i < len; i++) {
        unsigned char c = (unsigned char)str[i];
        if ((c & 0x80) == 0) cnt++;
        else if ((c & 0xE0) == 0xC0 && i + 1 < len) { cnt++; i++; }
        else if ((c & 0xF0) == 0xE0 && i + 2 < len) { cnt++; i += 2; }
        else if ((c & 0xF8) == 0xF0 && i + 3 < len) { cnt++; i += 3; }
    }
    return cnt;
}

bool minxg_utf8_is_valid(const char* str, size_t len) {
    size_t i;
    if (!str) return true;
    for (i = 0; i < len; i++) {
        unsigned char c = (unsigned char)str[i];
        if ((c & 0x80) == 0) continue;
        else if ((c & 0xE0) == 0xC0) {
            if (i + 1 >= len || (str[i+1] & 0xC0) != 0x80) return false;
            i++;
        } else if ((c & 0xF0) == 0xE0) {
            if (i + 2 >= len || (str[i+1] & 0xC0) != 0x80 || (str[i+2] & 0xC0) != 0x80) return false;
            i += 2;
        } else if ((c & 0xF8) == 0xF0) {
            if (i + 3 >= len || (str[i+1] & 0xC0) != 0x80 || (str[i+2] & 0xC0) != 0x80 || (str[i+3] & 0xC0) != 0x80) return false;
            i += 3;
        } else return false;
    }
    return true;
}

int minxg_utf8_grapheme_count(const char* str, size_t len) {
    return minxg_utf8_codepoint_count(str, len);
}

/* ─── CSV parser ─────────────────────────────────────────────────────── */

minxg_csv_reader_t minxg_csv_open(const char* data, size_t len, char delim) {
    minxg_csv_reader_t r = {0};
    r.data = data; r.len = len; r.pos = 0; r.row = 0; r.col = -1; r.delim = delim;
    return r;
}

int minxg_csv_next_cell(minxg_csv_reader_t* r, char* out_buf, size_t out_cap) {
    size_t start, p;
    if (!r || !out_buf || r->pos >= r->len) return -1;
    while (r->pos < r->len && r->data[r->pos] == ' ') r->pos++;
    start = r->pos;
    p = r->pos;
    if (r->data[p] == '"') {
        p++; start++;
        while (p + 1 < r->len) {
            if (r->data[p] == '"' && r->data[p+1] == '"') {
                if ((size_t)(p-start)+1 < out_cap) out_buf[p-start] = '"';
                p += 2;
            } else if (r->data[p] == '"') { break; }
            else {
                if ((size_t)(p-start) < out_cap) out_buf[p-start] = r->data[p];
                p++;
            }
        }
        while (p < r->len && (r->data[p] == ' ' || r->data[p] == '\t')) p++;
        if (p < r->len && r->data[p] != r->delim && r->data[p] != '\n' && r->data[p] != '\r') p++;
    } else {
        while (p < r->len && r->data[p] != r->delim && r->data[p] != '\n' && r->data[p] != '\r') p++;
    }
    {
        size_t cl = p - start;
        if (cl > out_cap - 1) cl = out_cap - 1;
        {
            size_t kk;
            for (kk = 0; kk < cl; kk++) out_buf[kk] = r->data[start + kk];
        }
        out_buf[cl] = '\0';
    }
    if (p < r->len && r->data[p] == r->delim) {
        p++; r->col++;
    } else if (p < r->len && (r->data[p] == '\n' || (r->data[p] == '\r' && !(p+1 < r->len && r->data[p+1] == '\n')))) {
        r->col = 0; r->row++;
        if (r->data[p] == '\r' && p + 1 < r->len && r->data[p+1] == '\n') p++;
        p++;
    }
    r->pos = p + 1;
    return (int)(p - start > (long)(out_cap - 1) ? out_cap - 1 : p - start);
}

void minxg_csv_count(const char* data, size_t len, char delim, int* out_rows, int* out_cols) {
    int rows = 1, cols = 0, cur = 1;
    size_t i;
    if (!data) { if (out_rows) *out_rows = 0; if (out_cols) *out_cols = 0; return; }
    for (i = 0; i < len; i++) {
        if (data[i] == delim) cur++;
        else if (data[i] == '\n') { if (cur > cols) cols = cur; cur = 1; rows++; }
        else if (data[i] == '\r' && i + 1 < len && data[i+1] == '\n') {
            if (cur > cols) cols = cur; cur = 1; rows++; i++;
        }
    }
    if (cur > cols) cols = cur;
    if (out_rows) *out_rows = rows;
    if (out_cols) *out_cols = cols;
}
