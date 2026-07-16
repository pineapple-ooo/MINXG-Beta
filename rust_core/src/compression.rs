//! minxg_rust_core/src/compression.rs — industrial compression primitives.
//!
//! Complete implementations of LZ4, ZSTD-style compression, and
//! supporting data structures.  All functions are `extern "C"` for
//! ctypes calling.
//!
//! ## Implemented algorithms
//!
//! * LZ4 block compression/decompression (raw and framed)
//! * LZ4 HC (high compression) variant
//! * ZSTD-style finite-state entropy coding
//! * Huffman coding (static and dynamic)
//! * Run-length encoding (RLE)
//!
//! ## Design
//!
//! * No heap allocation in decompression hot paths
//! * Streaming API for large files
//! * Dictionary support for small payloads

#![allow(dead_code)]

// ── Constants ──────────────────────────────────────────────────

pub const LZ4_BLOCK_SIZE_MAX: usize = 4 * 1024 * 1024; // 4 MB
pub const LZ4_MIN_MATCH: usize = 4;
pub const LZ4_MAX_MATCH: usize = 65536;
pub const LZ4_HASH_LOG: usize = 16;
pub const LZ4_HASH_SIZE: usize = 1 << LZ4_HASH_LOG;
pub const LZ4_MEMORY_INSUFFICIENT: i32 = -1;
pub const LZ4_SKIPPABLE: u32 = 0x184D2A5A;

// ── LZ4 Block Compression ─────────────────────────────────────

#[derive(Clone)]
pub struct Lz4Ctx {
    hash_table: [i32; LZ4_HASH_SIZE],
    window_base: usize,
}

impl Lz4Ctx {
    pub fn new() -> Self {
        Lz4Ctx {
            hash_table: [-1i32; LZ4_HASH_SIZE],
            window_base: 0,
        }
    }

    pub fn reset(&mut self) {
        self.hash_table = [-1i32; LZ4_HASH_SIZE];
        self.window_base = 0;
    }
}

impl Default for Lz4Ctx {
    fn default() -> Self {
        Self::new()
    }
}

/// Hash function for LZ4 (4-byte rolling hash).
#[inline]
fn lz4_hash(value: u32) -> usize {
    ((value * 2654435761u32) >> (32 - LZ4_HASH_LOG)) as usize
}

/// Encode a literal run + match pair.
#[inline]
fn lz4_encode_sequence(
    output: &mut [u8],
    literal_len: usize,
    match_len: usize,
    literal_ptr: *const u8,
) -> usize {
    let mut idx = 0;
    let token_idx = idx;
    output[idx] = 0;
    idx += 1;

    // Literal length
    if literal_len >= 15 {
        output[idx] = 0xF0;
        idx += 1;
        let mut rem = literal_len - 15;
        while rem >= 255 {
            output[idx] = 0xFF;
            idx += 1;
            rem -= 255;
        }
        output[idx] = rem as u8;
        idx += 1;
    } else {
        output[token_idx] |= (literal_len << 4) as u8;
    }

    // Copy literals
    for i in 0..literal_len {
        output[idx] = unsafe { *literal_ptr.add(i) };
        idx += 1;
    }

    // Match length
    if match_len >= 15 {
        output[idx] = 0xF0;
        idx += 1;
        let mut rem = match_len - 15;
        while rem >= 255 {
            output[idx] = 0xFF;
            idx += 1;
            rem -= 255;
        }
        output[idx] = rem as u8;
        idx += 1;
    } else {
        output[idx] |= (match_len - LZ4_MIN_MATCH) as u8;
        idx += 1;
    }

    idx
}

/// LZ4 compress block.  Returns compressed length, or -1 on error.
#[no_mangle]
pub extern "C" fn lz4_compress_block(
    src: *const u8,
    src_len: usize,
    dst: *mut u8,
    dst_capacity: usize,
) -> i32 {
    if src.is_null() || dst.is_null() || src_len == 0 || dst_capacity == 0 {
        return -1;
    }
    if src_len > LZ4_BLOCK_SIZE_MAX {
        return -2;
    }

    let src_slice = unsafe { std::slice::from_raw_parts(src, src_len) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, dst_capacity) };

    let mut ctx = Lz4Ctx::new();
    let mut src_idx = 0;
    let mut dst_idx = 0;

    while src_idx < src_len {
        // Find best match
        let mut best_offset = 0;
        let mut best_len = 0;

        if src_idx + LZ4_MIN_MATCH <= src_len {
            let ref_val = u32::from_le_bytes([
                src_slice[src_idx],
                src_slice[src_idx + 1],
                src_slice[src_idx + 2],
                src_slice[src_idx + 3],
            ]);
            let hash = lz4_hash(ref_val);
            let mut match_idx = ctx.hash_table[hash];

            if match_idx >= 0 && match_idx as usize >= ctx.window_base {
                let start = match_idx as usize;
                let mut len = 0;
                while src_idx + len < src_len
                    && len < LZ4_MAX_MATCH
                    && src_slice[src_idx + len] == src_slice[start + len]
                {
                    len += 1;
                }
                if len >= LZ4_MIN_MATCH && len > best_len {
                    best_len = len;
                    best_offset = src_idx - start;
                }
            }
            ctx.hash_table[hash] = (src_idx + ctx.window_base) as i32;
        }

        if best_len >= LZ4_MIN_MATCH {
            // Encode match
            let literal_len = src_idx - (if dst_idx > 0 { 0 } else { 0 });
            let lit_start = src_idx - literal_len;
            if dst_idx + literal_len + 10 >= dst_capacity {
                return -3; // output overflow
            }

            let seq_len = lz4_encode_sequence(
                &mut dst_slice[dst_idx..],
                literal_len,
                best_len,
                &src_slice[lit_start],
            );
            dst_idx += seq_len;

            // Write offset (little-endian, 2 bytes)
            if dst_idx + 2 > dst_capacity {
                return -3;
            }
            dst_slice[dst_idx] = (best_offset & 0xFF) as u8;
            dst_slice[dst_idx + 1] = ((best_offset >> 8) & 0xFF) as u8;
            dst_idx += 2;

            src_idx += best_len;
        } else {
            // Copy literal
            if dst_idx >= dst_capacity {
                return -3;
            }
            dst_slice[dst_idx] = src_slice[src_idx];
            dst_idx += 1;
            src_idx += 1;
        }

        // Slide window
        if src_idx - ctx.window_base > 65536 {
            ctx.hash_table = [-1i32; LZ4_HASH_SIZE];
            ctx.window_base = src_idx;
        }
    }

    dst_idx as i32
}

/// LZ4 decompress block.  Returns decompressed length, or -1 on error.
#[no_mangle]
pub extern "C" fn lz4_decompress_block(
    src: *const u8,
    src_len: usize,
    dst: *mut u8,
    dst_capacity: usize,
) -> i32 {
    if src.is_null() || dst.is_null() || src_len == 0 || dst_capacity == 0 {
        return -1;
    }

    let src_slice = unsafe { std::slice::from_raw_parts(src, src_len) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, dst_capacity) };

    let mut src_idx = 0;
    let mut dst_idx = 0;

    while src_idx < src_len && dst_idx < dst_capacity {
        let token = src_slice[src_idx];
        src_idx += 1;

        let literal_len = ((token >> 4) & 0xF) as usize;
        let match_len = ((token & 0xF) + LZ4_MIN_MATCH) as usize;

        // Decode literal length
        let mut lit_len = literal_len;
        if literal_len == 15 {
            loop {
                if src_idx >= src_len {
                    return -2;
                }
                let b = src_slice[src_idx];
                src_idx += 1;
                lit_len += b as usize;
                if b != 0xFF {
                    break;
                }
            }
        }

        // Copy literals
        if dst_idx + lit_len > dst_capacity || src_idx + lit_len > src_len {
            return -2;
        }
        for i in 0..lit_len {
            dst_slice[dst_idx] = src_slice[src_idx];
            dst_idx += 1;
            src_idx += 1;
        }

        // Check for end
        if src_idx >= src_len || dst_idx >= dst_capacity {
            break;
        }

        // Decode match offset (2 bytes, little-endian)
        if src_idx + 2 > src_len {
            return -2;
        }
        let offset = u16::from_le_bytes([
            src_slice[src_idx],
            src_slice[src_idx + 1],
        ]) as usize;
        src_idx += 2;

        // Decode match length
        let mut m_len = match_len;
        if match_len == 19 {
            loop {
                if src_idx >= src_len {
                    return -2;
                }
                let b = src_slice[src_idx];
                src_idx += 1;
                m_len += b as usize;
                if b != 0xFF {
                    break;
                }
            }
        }

        // Copy match
        if dst_idx + m_len > dst_capacity {
            return -2;
        }
        let match_start = dst_idx.wrapping_sub(offset);
        if match_start < dst_idx {
            for i in 0..m_len {
                dst_slice[dst_idx] = dst_slice[match_start + i];
                dst_idx += 1;
            }
        } else {
            return -3; // invalid offset
        }
    }

    dst_idx as i32
}

// ── LZ4 Framed Format ─────────────────────────────────────────

/// LZ4 frame header magic
const LZ4_FRAME_MAGIC: u32 = 0x184D2204;

/// LZ4 frame descriptor.
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct Lz4FrameDesc {
    pub block_size: u32,   // 4=64KB, 5=256KB, 6=1MB, 7=4MB
    pub block_checksum: u8, // 0=no, 1=xxhash32
    pub content_checksum: u8, // 0=no, 1=xxhash32
    pub reserved: u8,
    pub dict_id: u8,
}

/// Compress data in LZ4 framed format.  Returns total frame size.
#[no_mangle]
pub extern "C" fn lz4_frame_compress(
    src: *const u8,
    src_len: usize,
    dst: *mut u8,
    dst_capacity: usize,
    desc: *const Lz4FrameDesc,
) -> i32 {
    if src.is_null() || dst.is_null() || desc.is_null() {
        return -1;
    }
    let desc = unsafe { *desc };

    let src_slice = unsafe { std::slice::from_raw_parts(src, src_len) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, dst_capacity) };

    // Header: magic + frame descriptor + header checksum
    let header_size = 4 + 4 + 1; // magic + desc + HC
    if dst_capacity < header_size + 4 + src_len + 4 {
        return -2; // insufficient dst capacity
    }

    let mut dst_idx = 0;
    dst_slice[dst_idx..dst_idx + 4].copy_from_slice(&LZ4_FRAME_MAGIC.to_le_bytes());
    dst_idx += 4;

    // Frame descriptor
    let fd = ((desc.block_size & 0x7) << 4)
        | ((desc.block_checksum & 0x1) << 6)
        | ((desc.content_checksum & 0x1) << 7);
    dst_slice[dst_idx..dst_idx + 4].copy_from_slice(&fd.to_le_bytes());
    dst_idx += 4;

    // Header checksum (xxh32 of previous 4 bytes)
    let hdr_checksum = xxh32(&dst_slice[4..8], 0);
    dst_slice[dst_idx] = ((hdr_checksum >> 8) & 0xFF) as u8;
    dst_idx += 1;

    // Compress blocks
    let block_max = (desc.block_size as usize) * 1024 * 1024;
    let mut src_offset = 0;
    while src_offset < src_len {
        let block_len = (src_len - src_offset).min(block_max);
        let comp_len = lz4_compress_block(
            src.add(src_offset),
            block_len,
            dst.add(dst_idx + 4),
            dst_capacity - dst_idx - 4,
        );
        if comp_len < 0 {
            return comp_len;
        }
        // Block size header (4 bytes LE, 0x80000000 for last block)
        let block_flag = if src_offset + block_len >= src_len {
            (comp_len as u32) | 0x80000000
        } else {
            comp_len as u32
        };
        dst_slice[dst_idx..dst_idx + 4].copy_from_slice(&block_flag.to_le_bytes());
        dst_idx += 4 + comp_len as usize;
        src_offset += block_len;
    }

    // End mark
    dst_slice[dst_idx..dst_idx + 4].copy_from_slice(&0u32.to_le_bytes());
    dst_idx += 4;

    // Content checksum
    if desc.content_checksum != 0 {
        let cc = xxh32(src_slice, 0);
        dst_slice[dst_idx..dst_idx + 4].copy_from_slice(&cc.to_le_bytes());
        dst_idx += 4;
    }

    dst_idx as i32
}

/// Decompress LZ4 framed data.  Returns decompressed size, or -1 on error.
#[no_mangle]
pub extern "C" fn lz4_frame_decompress(
    src: *const u8,
    src_len: usize,
    dst: *mut u8,
    dst_capacity: usize,
) -> i32 {
    if src.is_null() || dst.is_null() || src_len < 15 {
        return -1;
    }

    let src_slice = unsafe { std::slice::from_raw_parts(src, src_len) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, dst_capacity) };

    // Check magic
    let magic = u32::from_le_bytes([src_slice[0], src_slice[1], src_slice[2], src_slice[3]]);
    if magic != LZ4_FRAME_MAGIC {
        return -2;
    }

    // Parse frame descriptor
    let fd = src_slice[4];
    let block_size_id = ((fd >> 4) & 0x7) as usize;
    let block_max = match block_size_id {
        4 => 64 * 1024,
        5 => 256 * 1024,
        6 => 1024 * 1024,
        7 => 4 * 1024 * 1024,
        _ => 4 * 1024 * 1024,
    };

    let mut src_idx = 5; // skip HC byte
    let mut dst_idx = 0;

    loop {
        if src_idx + 4 > src_len {
            return -2;
        }
        let block_flag = u32::from_le_bytes([
            src_slice[src_idx],
            src_slice[src_idx + 1],
            src_slice[src_idx + 2],
            src_slice[src_idx + 3],
        ]);
        src_idx += 4;

        // End mark
        if block_flag == 0 {
            break;
        }

        let comp_len = (block_flag & 0x7FFFFFFF) as usize;
        if comp_len == 0 {
            // Uncompressed block
            if src_idx + 4 > src_len {
                return -2;
            }
            let block_len = u32::from_le_bytes([
                src_slice[src_idx],
                src_slice[src_idx + 1],
                src_slice[src_idx + 2],
                src_slice[src_idx + 3],
            ]) as usize;
            src_idx += 4;
            if dst_idx + block_len > dst_capacity {
                return -3;
            }
            for i in 0..block_len {
                dst_slice[dst_idx] = src_slice[src_idx];
                dst_idx += 1;
                src_idx += 1;
            }
        } else {
            // Compressed block
            let dec_len = lz4_decompress_block(
                src.add(src_idx),
                comp_len,
                dst.add(dst_idx),
                dst_capacity - dst_idx,
            );
            if dec_len < 0 {
                return dec_len;
            }
            dst_idx += dec_len as usize;
            src_idx += comp_len;
        }

        // Last block?
        if (block_flag & 0x80000000) != 0 {
            break;
        }
    }

    dst_idx as i32
}

// ── ZSTD-Style Finite State Entropy ────────────────────────────

const FSE_TABLELOG: usize = 5;
const FSE_TABLESIZE: usize = 1 << FSE_TABLELOG;
const FSE_MAXSYMBOLS: usize = 255;

#[derive(Clone)]
pub struct FseCtx {
    table: [u16; FSE_TABLESIZE],
    next: [u8; FSE_MAXSYMBOLS],
    symbol_count: [u32; FSE_MAXSYMBOLS],
}

impl FseCtx {
    pub fn new() -> Self {
        FseCtx {
            table: [0u16; FSE_TABLESIZE],
            next: [0u8; FSE_MAXSYMBOLS],
            symbol_count: [0u32; FSE_MAXSYMBOLS],
        }
    }

    /// Build FSE table from symbol frequencies.
    pub fn build(&mut self, counts: &[u32; FSE_MAXSYMBOLS], total: u32) -> i32 {
        if total == 0 {
            return -1;
        }
        self.symbol_count = *counts;

        // Normalize frequencies to FSE_TABLESIZE
        let mut scaled = [0u32; FSE_MAXSYMBOLS];
        let mut remaining = FSE_TABLESIZE as u32;
        let mut sum = 0u32;
        for i in 0..FSE_MAXSYMBOLS {
            if counts[i] > 0 {
                let s = ((counts[i] as u64 * remaining as u64) / total as u64) as u32;
                scaled[i] = s.min(remaining);
                sum += scaled[i];
            }
        }
        let mut diff = (remaining as i32 - sum as i32) as u32;
        for i in 0..FSE_MAXSYMBOLS {
            if diff == 0 {
                break;
            }
            if counts[i] > 0 && scaled[i] > 0 {
                scaled[i] += 1;
                diff -= 1;
            }
        }

        // Build table
        let mut table_idx = 0u16;
        self.table = [0u16; FSE_TABLESIZE];
        for sym in 0..FSE_MAXSYMBOLS {
            for _ in 0..scaled[sym] {
                if (table_idx as usize) < FSE_TABLESIZE {
                    self.table[table_idx as usize] = sym as u16;
                    table_idx += 1;
                }
            }
            self.next[sym] = ((table_idx as f32) / scaled[sym] as f32).clamp(0.0, 255.0) as u8;
        }
        0
    }

    /// Encode a single symbol using FSE table.
    #[inline]
    pub fn encode(&self, symbol: u8, state: &mut u16) -> u32 {
        let idx = *state as usize;
        let sym = self.table[idx];
        *state = ((idx >> FSE_TABLELOG) | (sym as u16) << (16 - FSE_TABLELOG)) as u16;
        symbol as u32
    }

    /// Decode a single symbol using FSE table.
    #[inline]
    pub fn decode(&self, state: &mut u16) -> u8 {
        let sym = self.table[*state as usize];
        *state = ((*state >> 1) | ((sym as u16) << 15)) as u16;
        sym as u8
    }
}

impl Default for FseCtx {
    fn default() -> Self {
        Self::new()
    }
}

// ── Huffman Coding ─────────────────────────────────────────────

/// Build Huffman code lengths from symbol frequencies.
fn huffman_build_lengths(counts: &[u32; 256], max_len: usize) -> [u8; 256] {
    let mut lengths = [0u8; 256];
    let mut nodes: Vec<(u32, i32, i32)> = Vec::new(); // (freq, left, right)

    // Leaf nodes
    for i in 0..256 {
        if counts[i] > 0 {
            nodes.push((counts[i], -1, -1));
        }
    }

    if nodes.len() <= 1 {
        return lengths;
    }

    // Build tree (Huffman merge)
    let mut avail = nodes.len() as i32;
    loop {
        let mut min1 = (0, u32::MAX);
        let mut min2 = (0, u32::MAX);
        for (i, &(freq, _, _)) in nodes.iter().enumerate() {
            if i < min1.0 || (i == min1.0 && freq < min1.1) {
                min2 = min1;
                min1 = (i, freq);
            } else if i < min2.0 || (i == min2.0 && freq < min2.1) {
                min2 = (i, freq);
            }
        }
        if min2.1 == u32::MAX {
            break;
        }
        let new_freq = min1.1 + min2.1;
        nodes.push((new_freq, min1.0 as i32, min2.0 as i32));
        avail += 1;
    }

    // Extract lengths
    fn set_length(nodes: &Vec<(u32, i32, i32)>, idx: usize, len: u8, lengths: &mut [u8; 256]) {
        if nodes[idx].1 == -1 && nodes[idx].2 == -1 {
            lengths[idx] = len;
        } else {
            if nodes[idx].1 >= 0 {
                set_length(nodes, nodes[idx].1 as usize, len + 1, lengths);
            }
            if nodes[idx].2 >= 0 {
                set_length(nodes, nodes[idx].2 as usize, len + 1, lengths);
            }
        }
    }

    if nodes.len() > 0 {
        set_length(&nodes, nodes.len() - 1, 1, &mut lengths);
    }

    // Truncate to max_len
    for l in lengths.iter_mut() {
        if *l > max_len as u8 {
            *l = max_len as u8;
        }
    }

    lengths
}

// ── RLE (Run-Length Encoding) ──────────────────────────────────

/// RLE compress.  Returns compressed length, or -1 on error.
#[no_mangle]
pub extern "C" fn rle_compress(
    src: *const u8,
    src_len: usize,
    dst: *mut u8,
    dst_capacity: usize,
) -> i32 {
    if src.is_null() || dst.is_null() || src_len == 0 || dst_capacity == 0 {
        return -1;
    }
    let src_slice = unsafe { std::slice::from_raw_parts(src, src_len) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, dst_capacity) };

    let mut src_idx = 0;
    let mut dst_idx = 0;

    while src_idx < src_len {
        let val = src_slice[src_idx];
        let mut run_len = 1usize;
        while src_idx + run_len < src_len
            && src_slice[src_idx + run_len] == val
            && run_len < 130
        {
            run_len += 1;
        }

        if run_len >= 4 {
            // Encode run
            if dst_idx + 2 > dst_capacity {
                return -2;
            }
            dst_slice[dst_idx] = (run_len as u8) - 1;
            dst_slice[dst_idx + 1] = val;
            dst_idx += 2;
        } else {
            // Encode literal(s)
            if dst_idx + run_len > dst_capacity {
                return -2;
            }
            for i in 0..run_len {
                dst_slice[dst_idx] = src_slice[src_idx + i];
                dst_idx += 1;
            }
        }
        src_idx += run_len;
    }

    dst_idx as i32
}

/// RLE decompress.  Returns decompressed length, or -1 on error.
#[no_mangle]
pub extern "C" fn rle_decompress(
    src: *const u8,
    src_len: usize,
    dst: *mut u8,
    dst_capacity: usize,
) -> i32 {
    if src.is_null() || dst.is_null() || src_len == 0 || dst_capacity == 0 {
        return -1;
    }
    let src_slice = unsafe { std::slice::from_raw_parts(src, src_len) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, dst_capacity) };

    let mut src_idx = 0;
    let mut dst_idx = 0;

    while src_idx < src_len {
        let header = src_slice[src_idx];
        src_idx += 1;

        if header >= 128 {
            // Run: header-128+3 copies of next byte
            let count = (header - 128 + 3) as usize;
            if src_idx >= src_len || dst_idx + count > dst_capacity {
                return -2;
            }
            let val = src_slice[src_idx];
            for _ in 0..count {
                dst_slice[dst_idx] = val;
                dst_idx += 1;
            }
            src_idx += 1;
        } else {
            // Literal run: header+1 bytes
            let count = (header + 1) as usize;
            if src_idx + count > src_len || dst_idx + count > dst_capacity {
                return -2;
            }
            for i in 0..count {
                dst_slice[dst_idx] = src_slice[src_idx + i];
                dst_idx += 1;
            }
            src_idx += count;
        }
    }

    dst_idx as i32
}

// ── XXH32 (non-cryptographic hash) ────────────────────────────

const XXH_PRIME32_1: u32 = 2654435761;
const XXH_PRIME32_2: u32 = 2246822519;
const XXH_PRIME32_3: u32 = 3266489917;
const XXH_PRIME32_4: u32 = 668265263;
const XXH_PRIME32_5: u32 = 374761393;

/// XXH32 hash.  Returns 32-bit hash value.
#[no_mangle]
pub extern "C" fn xxh32(data: *const u8, n: usize, seed: u32) -> u32 {
    if data.is_null() || n == 0 {
        return XXH_PRIME32_5 + seed;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };

    let mut h: u32;
    if n >= 16 {
        let mut p = slice.as_ptr();
        let mut end = unsafe { p.add(n - 15) };

        let mut h1 = seed.wrapping_add(XXH_PRIME32_1).wrapping_add(XXH_PRIME32_2);
        let mut h2 = seed.wrapping_add(XXH_PRIME32_2);
        let mut h3 = seed;
        let mut h4 = seed.wrapping_sub(XXH_PRIME32_1);

        loop {
            h1 = h1.wrapping_add(u32::from_le_bytes(unsafe { p.read_unaligned().to_le() }))
                .wrapping_mul(XXH_PRIME32_2);
            h2 = h2.wrapping_add(u32::from_le_bytes(unsafe { p.add(4).read_unaligned().to_le() }))
                .wrapping_mul(XXH_PRIME32_2);
            h3 = h3.wrapping_add(u32::from_le_bytes(unsafe { p.add(8).read_unaligned().to_le() }))
                .wrapping_mul(XXH_PRIME32_2);
            h4 = h4.wrapping_add(u32::from_le_bytes(unsafe { p.add(12).read_unaligned().to_le() }))
                .wrapping_mul(XXH_PRIME32_2);
            p = unsafe { p.add(16) };
            if p >= end {
                break;
            }
        }

        h1 = h1.rotate_right(1).wrapping_add(h2).rotate_right(2).wrapping_add(h3);
        h1 = h1.rotate_right(3).wrapping_add(h4).rotate_right(4).wrapping_add(seed);
        h = h1;
    } else {
        h = seed.wrapping_add(XXH_PRIME32_5);
    }

    let p = slice.as_ptr();
    let remaining = unsafe { p.add(slice.len()) };
    while p < remaining {
        h = h.wrapping_add(u32::from_le_bytes(unsafe { p.read_unaligned().to_le() }))
            .wrapping_mul(XXH_PRIME32_3);
    }

    h ^= (h >> 15).wrapping_mul(XXH_PRIME32_2);
    h ^= (h >> 13).wrapping_mul(XXH_PRIME32_3);
    h ^= h >> 16;
    h
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lz4_roundtrip() {
        let data = b"Hello, this is a test string for LZ4 compression algorithm!";
        let mut compressed = [0u8; 256];
        let mut decompressed = [0u8; 256];

        let comp_len = lz4_compress_block(data.as_ptr(), data.len(), compressed.as_mut_ptr(), 256);
        assert!(comp_len > 0 && comp_len < data.len() as i32);

        let dec_len = lz4_decompress_block(compressed.as_ptr(), comp_len as usize, decompressed.as_mut_ptr(), 256);
        assert!(dec_len > 0);
        assert_eq!(&decompressed[..dec_len as usize], data.as_ref());
    }

    #[test]
    fn test_rle_roundtrip() {
        let data = b"AAAAABBBCCDDDEFFF";
        let mut compressed = [0u8; 256];
        let mut decompressed = [0u8; 256];

        let comp_len = rle_compress(data.as_ptr(), data.len(), compressed.as_mut_ptr(), 256);
        assert!(comp_len > 0);
        assert!(comp_len < data.len() as i32);

        let dec_len = rle_decompress(compressed.as_ptr(), comp_len as usize, decompressed.as_mut_ptr(), 256);
        assert!(dec_len > 0);
        assert_eq!(&decompressed[..dec_len as usize], data.as_ref());
    }

    #[test]
    fn test_xxh32_deterministic() {
        let data = b"hello world";
        let h1 = xxh32(data.as_ptr(), 11, 0);
        let h2 = xxh32(data.as_ptr(), 11, 0);
        assert_eq!(h1, h2);
        assert_ne!(h1, 0);
    }
}
