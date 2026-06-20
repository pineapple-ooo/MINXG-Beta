// cpp_wrapper.c — Plain C wrapper for libcore (ctypes interface)
//
// Pure C to avoid C++ name mangling. Python ctypes loads this directly.
//
// Memory ownership rules:
//   - Functions that return "allocated string" return malloc'd memory.
//     Caller must call cpp_free() to free.
//   - Functions with pre-allocated output buffers: caller owns the buffer.
//   - No RAII — use explicit cleanup functions.

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// ════════════════════════════════════════════════════════════════════════════════
// C++ internal headers (for inline implementations below)
// ════════════════════════════════════════════════════════════════════════════════
// We re-implement the hot paths in pure C+OpenSSL so there's no C++ linking dependency.

#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>
#include <openssl/bio.h>
#include <openssl/buffer.h>
#include <openssl/err.h>

#include "../c_core/text_engine.h"

// ── Internal helpers ──────────────────────────────────────────────────────────

static int base64_encode_buf(const uint8_t* in, size_t in_len, char* out, size_t out_cap) {
    BIO* b64 = BIO_new(BIO_f_base64());
    BIO* bio = BIO_new_fp(stdout, BIO_NOCLOSE); // unused
    (void)bio;
    BIO* bmem = BIO_new(BIO_s_mem());
    BIO* chain = BIO_push(b64, bmem);
    BIO_set_flags(b64, BIO_FLAGS_BASE64_NO_NL);
    BIO_write(chain, in, (int)in_len);
    BIO_flush(chain);
    BUF_MEM* bptr;
    BIO_get_mem_ptr(chain, &bptr);
    size_t needed = bptr->length + 1;
    if (needed > out_cap) { BIO_free_all(chain); return -1; }
    memcpy(out, bptr->data, bptr->length);
    out[bptr->length] = '\0';
    BIO_free_all(chain);
    return (int)bptr->length;
}

static int base64_decode_buf(const char* in, size_t in_len, uint8_t* out, size_t out_cap) {
    BIO* b64 = BIO_new(BIO_f_base64());
    BIO* bmem = BIO_new_mem_buf(in, (int)in_len);
    BIO* chain = BIO_push(b64, bmem);
    BIO_set_flags(b64, BIO_FLAGS_BASE64_NO_NL);
    int out_len = BIO_read(chain, out, (int)out_cap);
    BIO_free_all(chain);
    return out_len > 0 ? out_len : -1;
}

static int hex_encode_buf(const uint8_t* in, size_t in_len, char* out, size_t out_cap) {
    if (in_len * 2 + 1 > out_cap) return -1;
    for (size_t i = 0; i < in_len; i++) {
        snprintf(out + i*2, 3, "%02x", in[i]);
    }
    return (int)(in_len * 2);
}

static int url_encode_inplace(char* str, size_t len) {
    // Percent-encode special characters in place (conservative set)
    // Returns new length (may be longer than original)
    if (!str || len == 0) return -1;

    // First pass: count
    size_t needed = 0;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)str[i];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') {
            needed += 1;
        } else {
            needed += 3; // %XX
        }
    }

    if (needed > len) {
        // Need more space — not safe to do in-place. Return -2 to signal expansion needed.
        (void)needed;
        return -2;
    }

    // In-place replacement from end to start
    size_t wi = needed;
    for (size_t i = len; i > 0; i--) {
        unsigned char c = (unsigned char)str[i-1];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') {
            str[--wi] = (char)c;
        } else {
            str[--wi] = '%';
            str[--wi] = "0123456789ABCDEF"[c >> 4];
            str[--wi] = "0123456789ABCDEF"[c & 0xF];
        }
    }
    return (int)needed;
}

// ── URL decode (in-place) ──────────────────────────────────────────────────────
static int url_decode_inplace(char* str, size_t len) {
    if (!str) return -1;
    size_t ri = 0, wi = 0;
    for (size_t i = 0; i < len; i++) {
        if (str[i] == '%' && i + 2 < len) {
            int h = 0, l = 0;
            char hs = str[i+1], ls = str[i+2];
            if (hs >= '0' && hs <= '9') h = hs - '0';
            else if (hs >= 'A' && hs <= 'F') h = hs - 'A' + 10;
            else if (hs >= 'a' && hs <= 'f') h = hs - 'a' + 10;
            else { str[wi++] = str[i]; continue; }
            if (ls >= '0' && ls <= '9') l = ls - '0';
            else if (ls >= 'A' && ls <= 'F') l = ls - 'A' + 10;
            else if (ls >= 'a' && ls <= 'f') l = ls - 'a' + 10;
            else { str[wi++] = str[i]; continue; }
            str[wi++] = (char)((h << 4) | l);
            i += 2;
        } else if (str[i] == '+') {
            str[wi++] = ' ';
        } else {
            str[wi++] = str[i];
        }
    }
    str[wi] = '\0';
    return (int)wi;
}

// ════════════════════════════════════════════════════════════════════════════════
// Encoding
// ════════════════════════════════════════════════════════════════════════════════

int cpp_base64_encode(const uint8_t* in, size_t in_len, char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    return base64_encode_buf(in, in_len, out, out_cap);
}

int cpp_base64_decode(const char* in, size_t in_len, uint8_t* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    return base64_decode_buf(in, in_len, out, out_cap);
}

int cpp_hex_encode(const uint8_t* in, size_t in_len, char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    return hex_encode_buf(in, in_len, out, out_cap);
}

int cpp_hex_decode(const char* in, size_t in_len, uint8_t* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    // Convert hex string to bytes
    if (in_len % 2 != 0) return -1;
    size_t out_len = in_len / 2;
    if (out_len > out_cap) return -1;
    for (size_t i = 0; i < out_len; i++) {
        char hs = in[i*2], ls = in[i*2+1];
        int hv = 0, lv = 0;
        if (hs >= '0' && hs <= '9') hv = hs - '0';
        else if (hs >= 'A' && hs <= 'F') hv = hs - 'A' + 10;
        else if (hs >= 'a' && hs <= 'f') hv = hs - 'a' + 10;
        else return -1;
        if (ls >= '0' && ls <= '9') lv = ls - '0';
        else if (ls >= 'A' && ls <= 'F') lv = ls - 'A' + 10;
        else if (ls >= 'a' && ls <= 'f') lv = ls - 'a' + 10;
        else return -1;
        out[i] = (uint8_t)((hv << 4) | lv);
    }
    return (int)out_len;
}

char* cpp_url_encode(const char* in) {
    if (!in) return NULL;
    size_t len = strlen(in);
    // Count needed size
    size_t needed = 0;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)in[i];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~')
            needed += 1;
        else
            needed += 3;
    }
    char* out = (char*)malloc(needed + 1);
    if (!out) return NULL;
    size_t pos = 0;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)in[i];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') {
            out[pos++] = (char)c;
        } else {
            out[pos++] = '%';
            out[pos++] = "0123456789ABCDEF"[c >> 4];
            out[pos++] = "0123456789ABCDEF"[c & 0xF];
        }
    }
    out[pos] = '\0';
    return out;
}

char* cpp_url_decode(const char* in) {
    if (!in) return NULL;
    char* buf = strdup(in);
    if (!buf) return NULL;
    int len = url_decode_inplace(buf, strlen(buf));
    if (len < 0) { free(buf); return NULL; }
    return buf; // caller frees with cpp_free()
}

void cpp_free(char* s) {
    free(s);
}

int cpp_utf8_valid(const char* in, size_t len) {
    if (!in) return -1;
    for (size_t i = 0; i < len; ) {
        unsigned char c = (unsigned char)in[i];
        if (c < 0x80) {
            i++;
        } else if ((c & 0xE0) == 0xC0) {
            if (i + 1 >= len || (in[i+1] & 0xC0) != 0x80) return 0;
            i += 2;
        } else if ((c & 0xF0) == 0xE0) {
            if (i + 2 >= len || (in[i+1] & 0xC0) != 0x80 || (in[i+2] & 0xC0) != 0x80) return 0;
            i += 3;
        } else if ((c & 0xF8) == 0xF0) {
            if (i + 3 >= len || (in[i+1] & 0xC0) != 0x80 || (in[i+2] & 0xC0) != 0x80 || (in[i+3] & 0xC0) != 0x80) return 0;
            i += 4;
        } else {
            return 0;
        }
    }
    return 1;
}

// ════════════════════════════════════════════════════════════════════════════════
// Crypto — SHA-256/512, HMAC, PBKDF2, Secure RNG
// ════════════════════════════════════════════════════════════════════════════════

int cpp_sha256(const uint8_t* in, size_t in_len, uint8_t* out, size_t out_cap) {
    if (!out || out_cap < 32) return -1;
    if (!in && in_len > 0) return -1;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    if (!ctx) return -1;
    int ok = EVP_DigestInit_ex(ctx, EVP_sha256(), NULL) &&
             EVP_DigestUpdate(ctx, in, in_len) &&
             EVP_DigestFinal_ex(ctx, out, NULL);
    EVP_MD_CTX_free(ctx);
    return ok ? 0 : -1;
}

int cpp_sha512(const uint8_t* in, size_t in_len, uint8_t* out, size_t out_cap) {
    if (!out || out_cap < 64) return -1;
    if (!in && in_len > 0) return -1;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    if (!ctx) return -1;
    int ok = EVP_DigestInit_ex(ctx, EVP_sha512(), NULL) &&
             EVP_DigestUpdate(ctx, in, in_len) &&
             EVP_DigestFinal_ex(ctx, out, NULL);
    EVP_MD_CTX_free(ctx);
    return ok ? 0 : -1;
}

int cpp_hmac_sha256(const uint8_t* key, size_t key_len,
                    const uint8_t* in, size_t in_len,
                    uint8_t* out, size_t out_cap) {
    if (!out || out_cap < 32) return -1;
    unsigned int out_len = 0;
    uint8_t* result = HMAC(EVP_sha256(),
                           key, (int)key_len,
                           in, in_len,
                           out, &out_len);
    return (result != NULL && out_len == 32) ? 0 : -1;
}

int cpp_pbkdf2_sha256(const uint8_t* password, size_t password_len,
                       const uint8_t* salt, size_t salt_len,
                       int iterations,
                       uint8_t* out, size_t out_cap) {
    if (!out) return -1;
    int ok = PKCS5_PBKDF2_HMAC((const char*)password, (int)password_len,
                                salt, (int)salt_len,
                                iterations,
                                EVP_sha256(),
                                (int)out_cap, out);
    return ok ? 0 : -1;
}

int cpp_secure_random(uint8_t* out, size_t len) {
    if (!out || len == 0) return -1;
    return RAND_bytes(out, (int)len) == 1 ? 0 : -1;
}

// ════════════════════════════════════════════════════════════════════════════════
// File Operations (POSIX)
// ════════════════════════════════════════════════════════════════════════════════

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

int cpp_file_stat(const char* path, uint64_t* out_size) {
    if (!path) return -1;
    struct stat st;
    if (stat(path, &st) != 0) return 0;
    if (!S_ISREG(st.st_mode)) return 0;
    if (out_size) *out_size = (uint64_t)st.st_size;
    return 1;
}

int cpp_file_copy(const char* src, const char* dst, uint64_t* out_bytes) {
    if (!src || !dst) return -1;
    int fin = open(src, O_RDONLY);
    if (fin < 0) return -1;
    int fout = open(dst, O_WRONLY|O_CREAT|O_TRUNC, 0644);
    if (fout < 0) { close(fin); return -1; }
    uint8_t buf[65536];
    ssize_t r;
    uint64_t total = 0;
    while ((r = read(fin, buf, sizeof(buf))) > 0) {
        ssize_t w = write(fout, buf, (size_t)r);
        if (w < 0) { close(fin); close(fout); return -1; }
        total += (uint64_t)w;
    }
    close(fin);
    close(fout);
    if (r < 0) return -1;
    if (out_bytes) *out_bytes = total;
    return 0;
}

int cpp_file_read(const char* path, uint8_t* out, size_t out_cap, uint64_t* out_read) {
    if (!path || !out || out_cap == 0) return -1;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    ssize_t r = read(fd, out, out_cap);
    close(fd);
    if (r < 0) return -1;
    if (out_read) *out_read = (uint64_t)r;
    return 0;
}

int cpp_file_write(const char* path, const uint8_t* in, size_t in_len) {
    if (!path || !in) return -1;
    int fd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
    if (fd < 0) return -1;
    ssize_t w = write(fd, in, in_len);
    close(fd);
    return (w == (ssize_t)in_len) ? 0 : -1;
}

// Memory-mapped file read
// Stores mapping in static registry; caller uses cpp_mmap_close to release
// Registry supports up to 64 concurrent mappings
#include <sys/mman.h>

typedef struct {
    void* addr;
    size_t len;
    int fd;
} MmapEntry;

static MmapEntry g_mmaps[64];
static int g_mmap_count = 0;

int cpp_mmap_read(const char* path, uint8_t** out_ptr, size_t* out_size) {
    if (!path || !out_ptr || !out_size) return -1;
    if (g_mmap_count >= 64) return -1;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) { close(fd); return -1; }
    size_t len = (size_t)st.st_size;
    void* addr = mmap(NULL, len, PROT_READ, MAP_PRIVATE, fd, 0);
    if (addr == MAP_FAILED) { close(fd); return -1; }
    close(fd); // fd can be closed after mmap
    int idx = g_mmap_count++;
    g_mmaps[idx].addr = addr;
    g_mmaps[idx].len = len;
    *out_ptr = (uint8_t*)addr;
    *out_size = len;
    return 0;
}

void cpp_mmap_close(void) {
    for (int i = 0; i < g_mmap_count; i++) {
        if (g_mmaps[i].addr) {
            munmap(g_mmaps[i].addr, g_mmaps[i].len);
            g_mmaps[i].addr = NULL;
        }
    }
    g_mmap_count = 0;
}

// Glob search
#include <glob.h>

int cpp_glob(const char* pattern, char* out, size_t out_cap, int max_results) {
    if (!pattern || !out || out_cap == 0) return -1;
    glob_t gl;
    int flags = glob(pattern, 0, NULL, &gl);
    if (flags != 0) {
        if (flags == GLOB_NOMATCH) { out[0] = '\0'; return 0; }
        return -1;
    }
    size_t pos = 0;
    int count = 0;
    for (size_t i = 0; i < gl.gl_pathc && (max_results == 0 || count < max_results); i++) {
        const char* p = gl.gl_pathv[i];
        size_t plen = strlen(p);
        if (pos + plen + 2 > out_cap) break;
        memcpy(out + pos, p, plen);
        pos += plen;
        out[pos++] = '\0';
        count++;
    }
    if (pos < out_cap) out[pos] = '\0';
    globfree(&gl);
    return count;
}

// ════════════════════════════════════════════════════════════════════════════════
// Data Processing (pure C)
// ════════════════════════════════════════════════════════════════════════════════

static int csv_count_cols(const char* line, size_t len, char delim) {
    int count = 1;
    for (size_t i = 0; i < len; i++) {
        if (line[i] == delim) count++;
    }
    return count;
}

int cpp_csv_info(const char* in, size_t in_len, char delim,
                 int* out_rows, int* out_cols) {
    if (!in || !out_rows || !out_cols) return -1;
    const char* start = in;
    const char* end = in + in_len;
    int rows = 0, cols = 0;
    const char* line_start = start;
    while (line_start < end) {
        const char* line_end = line_start;
        while (line_end < end && *line_end != '\n' && *line_end != '\r') line_end++;
        size_t line_len = line_end - line_start;
        while (line_len > 0 && (line_start[line_len-1] == '\n' || line_start[line_len-1] == '\r')) line_len--;
        if (line_len > 0) {
            if (rows == 0) cols = csv_count_cols(line_start, line_len, delim);
            rows++;
        }
        line_start = line_end;
        if (line_start < end && (*line_start == '\n' || *line_start == '\r')) line_start++;
    }
    *out_rows = rows;
    *out_cols = cols;
    return 0;
}

int cpp_csv_cell(const char* in, size_t in_len, char delim,
                 int row, int col,
                 char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    const char* start = in;
    const char* end = in + in_len;
    int cur_row = 0;
    const char* line_start = start;
    while (line_start < end) {
        const char* line_end = line_start;
        while (line_end < end && *line_end != '\n' && *line_end != '\r') line_end++;
        size_t line_len = line_end - line_start;
        while (line_len > 0 && (line_start[line_len-1] == '\n' || line_start[line_len-1] == '\r')) line_len--;
        if (line_len > 0 && cur_row == row) {
            int cur_col = 0;
            size_t cell_start = 0;
            for (size_t i = 0; i < line_len; i++) {
                if (line_start[i] == delim) {
                    if (cur_col == col) break;
                    cur_col++;
                    cell_start = i + 1;
                } else if (cur_col == col) {
                    // inside target cell
                }
            }
            size_t cell_len = (cur_col == col) ? (line_start + line_len - (line_start + cell_start)) : 0;
            if (cell_len >= out_cap) return -1;
            memcpy(out, line_start + cell_start, cell_len);
            out[cell_len] = '\0';
            return (int)cell_len;
        }
        line_start = line_end;
        if (line_start < end && (*line_start == '\n' || *line_start == '\r')) line_start++;
        cur_row++;
    }
    return -2; // out of bounds
}

int cpp_tokenize(const char* in, size_t in_len, char** out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    size_t count = 0;
    size_t i = 0;
    while (i < in_len && count < out_cap) {
        // skip whitespace
        while (i < in_len && (in[i] == ' ' || in[i] == '\t' || in[i] == '\n' || in[i] == '\r')) i++;
        if (i >= in_len) break;
        size_t start = i;
        while (i < in_len && in[i] != ' ' && in[i] != '\t' && in[i] != '\n' && in[i] != '\r') i++;
        size_t len = i - start;
        if (len > 0) {
            out[count] = (char*)malloc(len + 1);
            if (!out[count]) return -1;
            memcpy(out[count], in + start, len);
            out[count][len] = '\0';
            count++;
        }
    }
    return (int)count;
}

void cpp_free_string_array(char** arr, int len) {
    for (int i = 0; i < len; i++) free(arr[i]);
}

int cpp_word_frequency(const char* in, size_t in_len, int top_n,
                       char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    // Simple word frequency using a fixed-size hash table
    // Max 1024 unique words, 64 char max per word
    typedef struct { char word[64]; int count; int used; } Entry;
    Entry table[1024];
    memset(table, 0, sizeof(table));
    int num_words = 0;

    size_t i = 0;
    while (i < in_len) {
        while (i < in_len && (in[i] == ' ' || in[i] == '\t' || in[i] == '\n' || in[i] == '\r')) i++;
        if (i >= in_len) break;
        size_t start = i;
        while (i < in_len && in[i] != ' ' && in[i] != '\t' && in[i] != '\n' && in[i] != '\r') i++;
        size_t len = i - start;
        if (len == 0 || len >= 64) continue;
        char word[64];
        memcpy(word, in + start, len);
        word[len] = '\0';
        // Find in table
        int found = -1;
        for (int j = 0; j < num_words; j++) {
            if (strcmp(table[j].word, word) == 0) { found = j; break; }
        }
        if (found >= 0) {
            table[found].count++;
        } else if (num_words < 1024) {
            /* input len is bounded (<64) earlier in the loop so
             * `len` fits in `word[64]`; use memcpy + NUL to avoid
             * any future regression where the bound slips. */
            memcpy(table[num_words].word, word, len);
            table[num_words].word[len] = '\0';
            table[num_words].count = 1;
            table[num_words].used = 1;
            num_words++;
        }
    }

    // Selection sort top N by count
    for (int pass = 0; pass < top_n && pass < num_words; pass++) {
        int best = pass;
        for (int j = pass + 1; j < num_words; j++) {
            if (table[j].count > table[best].count) best = j;
        }
        if (best != pass) {
            Entry tmp = table[pass];
            table[pass] = table[best];
            table[best] = tmp;
        }
    }

    // Format output
    size_t pos = 0;
    int count = 0;
    for (int j = 0; j < num_words && count < top_n; j++) {
        char entry[96];
        int len = snprintf(entry, sizeof(entry), "%s:%d", table[j].word, table[j].count);
        if (len <= 0) continue;
        if (pos + (size_t)len + 1 > out_cap) break;
        memcpy(out + pos, entry, (size_t)len);
        pos += (size_t)len;
        out[pos++] = ',';
        count++;
    }
    if (pos > 0 && out[pos-1] == ',') pos--;
    if (pos < out_cap) out[pos] = '\0';
    return count;
}

int cpp_trim(const char* in, size_t in_len, char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    size_t start = 0, end = in_len;
    while (start < end && (in[start] == ' ' || in[start] == '\t' || in[start] == '\n' || in[start] == '\r')) start++;
    while (end > start && (in[end-1] == ' ' || in[end-1] == '\t' || in[end-1] == '\n' || in[end-1] == '\r')) end--;
    size_t len = end - start;
    if (len >= out_cap) return -1;
    if (len > 0) memcpy(out, in + start, len);
    out[len] = '\0';
    return (int)len;
}

// ════════════════════════════════════════════════════════════════════════════════
// v0.0.2: Extended text and math utilities (thin wrappers over text_engine C code)
// ════════════════════════════════════════════════════════════════════════════════

int cpp_slugify(const char* in, size_t in_len, char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    size_t w = (size_t)minxg_slugify(in, in_len, out, out_cap);
    return (int)w;
}

int cpp_truncate(const char* in, size_t in_len, size_t max_len,
                 const char* suffix, size_t suf_len,
                 char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    size_t w = minxg_truncate(in, in_len, max_len, suffix, suf_len, out, out_cap);
    return (int)w;
}

int cpp_extract_urls(const char* in, size_t in_len,
                     char* out, size_t out_cap, int max_urls) {
    return minxg_extract_urls(in, in_len, out, out_cap, max_urls);
}

int cpp_extract_emails(const char* in, size_t in_len,
                       char* out, size_t out_cap, int max_emails) {
    return minxg_extract_emails(in, in_len, out, out_cap, max_emails);
}

int cpp_extract_hashtags(const char* in, size_t in_len,
                         char* out, size_t out_cap, int max_tags) {
    return minxg_extract_hashtags(in, in_len, out, out_cap, max_tags);
}

int cpp_normalize_ws(const char* in, size_t in_len, int line_ending,
                     char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return -1;
    size_t w = minxg_normalize_ws(in, in_len, line_ending, out, out_cap);
    return (int)w;
}

int cpp_base_convert(const char* number, int base_fr, int base_to,
                     char* out, size_t out_cap) {
    return minxg_base_convert(number, base_fr, base_to, out, out_cap);
}

int cpp_word_freq_hash(const char* in, size_t in_len, int top_n,
                       char* out, size_t out_cap) {
    if (!in || !out || out_cap == 0) return 0;
    size_t w = minxg_word_freq_hash(in, in_len, top_n, out, out_cap);
    return w > 0 ? (int)top_n : 0;  // return number of entries
}