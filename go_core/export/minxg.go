// Package export provides C-exported functions for MINXG Go core.
// Build: go build -buildmode=c-shared -o ../../libminxg_go.so .
package main

/*
#cgo LDFLAGS: -L/storage/emulated/0/MINXG-Beta-0.11.0 -lminxg_c -lminxg_core -lpthread
#cgo CFLAGS: -I/storage/emulated/0/MINXG-Beta-0.11.0/c_core -I/storage/emulated/0/MINXG-Beta-0.11.0/cpp_core
#include <stdlib.h>
#include <text_engine.h>
#include <minxg_arch.h>
#include <mem_pool.h>

// Extra Go-side utilities (pure Go, no C dependency)
#include <string.h>
*/
import "C"
import (
	"runtime"
	"unsafe"
)

// GoVersion returns the Go runtime version string.
func version() string { return runtime.Version() }

//export MinxgGoVersion
func MinxgGoVersion() *C.char {
	return C.CString(version())
}

//export MinxgHealthCheck
func MinxgHealthCheck() C.int {
	return 1
}

//export MinxgTextSearchBMH
// Returns first match offset or -1. Pure C implementation.
func MinxgTextSearchBMH(haystack *C.char, hlen C.size_t, needle *C.char, nlen C.size_t) C.longlong {
	if haystack == nil || needle == nil || nlen == 0 || hlen < nlen {
		return C.longlong(-1)
	}
	pos := C.minxg_memmem((*C.uchar)(unsafe.Pointer(haystack)), hlen,
		(*C.uchar)(unsafe.Pointer(needle)), nlen)
	return C.longlong(pos)
}

//export MinxgTextSearchBMHReverse
// Returns last match offset or -1.
func MinxgTextSearchBMHReverse(haystack *C.char, hlen C.size_t, needle *C.char, nlen C.size_t) C.longlong {
	if haystack == nil || needle == nil || nlen == 0 || hlen < nlen {
		return C.longlong(-1)
	}
	pos := C.minxg_memrmem((*C.uchar)(unsafe.Pointer(haystack)), hlen,
		(*C.uchar)(unsafe.Pointer(needle)), nlen)
	return C.longlong(pos)
}

//export MinxgTextCount
// Count occurrences of needle in haystack.
func MinxgTextCount(haystack *C.char, hlen C.size_t, needle *C.char, nlen C.size_t) C.int {
	if haystack == nil || needle == nil || nlen == 0 || hlen < nlen {
		return 0
	}
	return C.int(C.minxg_memcnt((*C.uchar)(unsafe.Pointer(haystack)), hlen,
		(*C.uchar)(unsafe.Pointer(needle)), nlen))
}

//export MinxgStrLower
// In-place lowercase. Returns new length.
func MinxgStrLower(str *C.char, len C.size_t) C.size_t {
	if str == nil || len == 0 {
		return 0
	}
	return C.minxg_str_lower(str, len)
}

//export MinxgStrUpper
// In-place uppercase. Returns new length.
func MinxgStrUpper(str *C.char, len C.size_t) C.size_t {
	if str == nil || len == 0 {
		return 0
	}
	return C.minxg_str_upper(str, len)
}

//export MinxgStrTrim
// In-place trim. Returns new length.
func MinxgStrTrim(str *C.char, len C.size_t) C.size_t {
	if str == nil || len == 0 {
		return 0
	}
	return C.minxg_str_trim(str, len)
}

//export MinxgGlobMatch
// Returns 1 if pattern matches str, 0 otherwise.
func MinxgGlobMatch(pattern, str *C.char) C.int {
	if pattern == nil || str == nil {
		return 0
	}
	if C.minxg_fnmatch(pattern, str) {
		return 1
	}
	return 0
}

//export MinxgGlobMatchCI
// Case-insensitive glob match.
func MinxgGlobMatchCI(pattern, str *C.char) C.int {
	if pattern == nil || str == nil {
		return 0
	}
	if C.minxg_fnmatch_caseless(pattern, str) {
		return 1
	}
	return 0
}

//export MinxgUtf8Valid
// Returns 1 if valid UTF-8, 0 otherwise.
func MinxgUtf8Valid(str *C.char, len C.size_t) C.int {
	if str == nil || len == 0 {
		return 1
	}
	if C.minxg_utf8_is_valid(str, len) {
		return 1
	}
	return 0
}

//export MinxgUtf8Codepoints
// Returns number of Unicode codepoints.
func MinxgUtf8Codepoints(str *C.char, len C.size_t) C.int {
	if str == nil || len == 0 {
		return 0
	}
	return C.int(C.minxg_utf8_codepoint_count(str, len))
}

//export MinxgSlugify
// Slugify input: lowercase, strip non-word, collapse dashes.
// Returns bytes written to out_buf.
func MinxgSlugify(input *C.char, inLen C.size_t, outBuf *C.char, outCap C.size_t) C.size_t {
	if input == nil || inLen == 0 || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.minxg_slugify(input, inLen, outBuf, outCap)
}

//export MinxgTruncate
// Truncate input to maxLen, append suffix if truncated.
// Returns final length.
func MinxgTruncate(input *C.char, inLen C.size_t, maxLen C.size_t,
	suffix *C.char, sufLen C.size_t,
	outBuf *C.char, outCap C.size_t) C.size_t {
	if input == nil || inLen == 0 || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.minxg_truncate(input, inLen, maxLen, suffix, sufLen, outBuf, outCap)
}

//export MinxgWordFreqHash
// Word frequency analysis. out_buf gets "word1:N1,word2:N2,..." sorted desc.
// Returns bytes written, 0 on error.
func MinxgWordFreqHash(input *C.char, inLen C.size_t, topN C.int,
	outBuf *C.char, outCap C.size_t) C.size_t {
	if input == nil || inLen == 0 || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.minxg_word_freq_hash(input, inLen, topN, outBuf, outCap)
}

//export MinxgNormalizeWS
// Normalize whitespace: trim, collapse spaces, unify line endings.
// line_ending: 0='\n', 1='\r\n', 2='\r'.
// Returns final length.
func MinxgNormalizeWS(input *C.char, inLen C.size_t, lineEnding C.int,
	outBuf *C.char, outCap C.size_t) C.size_t {
	if input == nil || inLen == 0 || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.minxg_normalize_ws(input, inLen, lineEnding, outBuf, outCap)
}

//export MinxgBaseConvert
// Convert number string from base_fr to base_to. Supports 2-36.
// Returns length of result (0 on error).
func MinxgBaseConvert(number *C.char, baseFr C.int, baseTo C.int,
	outBuf *C.char, outCap C.size_t) C.int {
	if number == nil || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.minxg_base_convert(number, baseFr, baseTo, outBuf, outCap)
}

//export MinxgExtractURLs
// Extract HTTP/HTTPS URLs from input. Returns count.
// out_buf receives null-separated list.
func MinxgExtractURLs(input *C.char, inLen C.size_t,
	outBuf *C.char, outCap C.size_t, maxUrls C.int) C.int {
	if input == nil || inLen == 0 || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.int(C.minxg_extract_urls(input, inLen, outBuf, outCap, maxUrls))
}

//export MinxgExtractEmails
// Extract email addresses. Returns count.
func MinxgExtractEmails(input *C.char, inLen C.size_t,
	outBuf *C.char, outCap C.size_t, maxEmails C.int) C.int {
	if input == nil || inLen == 0 || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.int(C.minxg_extract_emails(input, inLen, outBuf, outCap, maxEmails))
}

//export MinxgExtractHashtags
// Extract #hashtags. Returns count.
func MinxgExtractHashtags(input *C.char, inLen C.size_t,
	outBuf *C.char, outCap C.size_t, maxTags C.int) C.int {
	if input == nil || inLen == 0 || outBuf == nil || outCap == 0 {
		return 0
	}
	return C.int(C.minxg_extract_hashtags(input, inLen, outBuf, outCap, maxTags))
}

//export MinxgArenaStats
// Returns arena stats: total, used, blockCount as 3 values.
// Takes arena pointer (from MinxgArenaCreate) as opaque uint64.
func MinxgArenaStats(arenaPtr uint64) (total, used, blocks C.int) {
	// Note: we'd need to reconstruct *C.minxg_arena_t from uint64
	// For now return zeros as placeholder (real impl would store map[uint64]*C.minxg_arena_t)
	return 0, 0, 0
}

//export MinxgFree
// Free C-allocated memory (for strings returned to Go caller).
func MinxgFree(ptr unsafe.Pointer) {
	C.free(ptr)
}

func main() {} // Required for c-shared
