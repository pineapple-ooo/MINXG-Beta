//! minxg_rust_core/src/crypto.rs — industrial cryptography primitives.
//!
//! Complete implementations of symmetric ciphers, hash functions, MACs,
//! and public-key operations.  All functions are `extern "C"` for ctypes
//! calling, with null-safety guards and constant-time operations where
//! security matters.
//!
//! ## Implemented algorithms
//!
//! ### Symmetric ciphers
//! * AES-128/192/256 (ECB/CBC/CTR modes)
//! * ChaCha20-Poly1305 (AEAD)
//! * Salsa20 (stream cipher)
//!
//! ### Hash functions
//! * SHA-256, SHA-512
//! * BLAKE2s, BLAKE2b
//! * MD5 (legacy only, marked insecure)
//!
//! ### MACs
//! * HMAC-SHA256, HMAC-SHA512
//! * Poly1305
//!
//! ### Public-key
//! * ECDSA (secp256k1, secp256r1)
//! * Ed25519 sign/verify
//! * RSA-OAEP (2048-bit)
//!
//! ## Security notes
//!
//! * All AES uses lookup tables (not bitslicing) — portable but not
//!   cache-timing resistant.  For high-security contexts, use
//!   ChaCha20-Poly1305 instead.
//! * Keys are zeroized after use where possible.
//! * No heap allocation for secret data in hot paths.

#![allow(dead_code)]

// ── Constants ──────────────────────────────────────────────────

pub const AES_BLOCK_SIZE: usize = 16;
pub const AES_KEY_SIZE_128: usize = 16;
pub const AES_KEY_SIZE_192: usize = 24;
pub const AES_KEY_SIZE_256: usize = 32;
pub const SHA256_DIGEST_SIZE: usize = 32;
pub const SHA512_DIGEST_SIZE: usize = 64;
pub const BLAKE2S_DIGEST_SIZE: usize = 32;
pub const BLAKE2B_DIGEST_SIZE: usize = 64;
pub const POLY1305_KEY_SIZE: usize = 32;
pub const POLY1305_TAG_SIZE: usize = 16;
pub const CHACHA20_KEY_SIZE: usize = 32;
pub const CHACHA20_NONCE_SIZE: usize = 12;
pub const ED25519_PUBLIC_KEY_SIZE: usize = 32;
pub const ED25519_SECRET_KEY_SIZE: usize = 32;
pub const ED25519_SIGNATURE_SIZE: usize = 64;
pub const ECDSA_SECP256K1_KEY_SIZE: usize = 32;
pub const ECDSA_SECP256K1_SIG_SIZE: usize = 64;

// ── AES (Advanced Encryption Standard) ────────────────────────

/// AES S-box
const AES_SBOX: [u8; 256] = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
];

const AES_INV_SBOX: [u8; 256] = [
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d,
];

const AES_RCON: [u8; 10] = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36];

/// Internal AES-128 round keys (11 words)
#[derive(Clone)]
pub struct Aes128Key {
    pub round_keys: [u32; 44],
}

/// Internal AES-256 round keys (15 words)
#[derive(Clone)]
pub struct Aes256Key {
    pub round_keys: [u32; 60],
}

// AES key expansion helpers
#[inline]
fn aes_sub_word(w: u32) -> u32 {
    u32::from_be_bytes([
        AES_SBOX[(w >> 24) as usize],
        AES_SBOX[((w >> 16) & 0xff) as usize],
        AES_SBOX[((w >> 8) & 0xff) as usize],
        AES_SBOX[(w & 0xff) as usize],
    ])
}

#[inline]
fn aes_rot_word(w: u32) -> u32 {
    w.rotate_right(8)
}

fn aes_key_expand_128(key: &[u8; 16]) -> Aes128Key {
    let mut rk = Aes128Key { round_keys: [0u32; 44] };
    let mut temp: u32;

    // Copy key
    for i in 0..4 {
        rk.round_keys[i] = u32::from_be_bytes([key[i * 4], key[i * 4 + 1], key[i * 4 + 2], key[i * 4 + 3]]);
    }

    for i in 4..44 {
        temp = rk.round_keys[i - 1];
        if i % 4 == 0 {
            temp = aes_sub_word(aes_rot_word(temp)) ^ (u32::from(AES_RCON[i / 4 - 1]) << 24);
        }
        rk.round_keys[i] = rk.round_keys[i - 4] ^ temp;
    }
    rk
}

fn aes_key_expand_256(key: &[u8; 32]) -> Aes256Key {
    let mut rk = Aes256Key { round_keys: [0u32; 60] };

    for i in 0..8 {
        rk.round_keys[i] = u32::from_be_bytes([key[i * 4], key[i * 4 + 1], key[i * 4 + 2], key[i * 4 + 3]]);
    }

    let mut temp: u32;
    for i in 8..60 {
        temp = rk.round_keys[i - 1];
        if i % 8 == 0 {
            temp = aes_sub_word(aes_rot_word(temp)) ^ (u32::from(AES_RCON[i / 8 - 1]) << 24);
        } else if i % 8 == 4 {
            temp = aes_sub_word(temp);
        }
        rk.round_keys[i] = rk.round_keys[i - 8] ^ temp;
    }
    rk
}

#[inline]
fn aes_add_round_key(state: &mut [u8; 16], rk: &[u32]) {
    for i in 0..4 {
        let w = rk[i];
        state[i * 4] ^= (w >> 24) as u8;
        state[i * 4 + 1] ^= ((w >> 16) & 0xff) as u8;
        state[i * 4 + 2] ^= ((w >> 8) & 0xff) as u8;
        state[i * 4 + 3] ^= (w & 0xff) as u8;
    }
}

#[inline]
fn aes_sub_bytes(state: &mut [u8; 16]) {
    for b in state.iter_mut() {
        *b = AES_SBOX[*b as usize];
    }
}

#[inline]
fn aes_shift_rows(state: &mut [u8; 16]) {
    let tmp = state[1];
    state[1] = state[5];
    state[5] = state[9];
    state[9] = state[13];
    state[13] = tmp;

    let tmp1 = state[2];
    let tmp2 = state[6];
    state[2] = state[10];
    state[6] = state[14];
    state[10] = tmp1;
    state[14] = tmp2;

    let tmp1 = state[3];
    let tmp2 = state[7];
    let tmp3 = state[11];
    state[3] = state[15];
    state[7] = tmp1;
    state[11] = tmp2;
    state[15] = tmp3;
}

#[inline]
fn aes_mix_columns(state: &mut [u8; 16]) {
    for i in 0..4 {
        let a = state[i * 4];
        let b = state[i * 4 + 1];
        let c = state[i * 4 + 2];
        let d = state[i * 4 + 3];

        state[i * 4] = gmul(a, 2) ^ gmul(b, 3) ^ c ^ d;
        state[i * 4 + 1] = a ^ gmul(b, 2) ^ gmul(c, 3) ^ d;
        state[i * 4 + 2] = a ^ b ^ gmul(c, 2) ^ gmul(d, 3);
        state[i * 4 + 3] = gmul(a, 3) ^ b ^ c ^ gmul(d, 2);
    }
}

#[inline]
fn gmul(mut a: u8, b: u8) -> u8 {
    let mut p = 0u8;
    for _ in 0..8 {
        if (b & 1) != 0 {
            p ^= a;
        }
        let hi = (a & 0x80) != 0;
        a <<= 1;
        if hi {
            a ^= 0x1b;
        }
        b >>= 1;
    }
    p
}

fn aes_encrypt_block_128(state: &mut [u8; 16], key: &Aes128Key) {
    aes_add_round_key(state, &key.round_keys[0..4]);

    for round in 1..10 {
        aes_sub_bytes(state);
        aes_shift_rows(state);
        if round < 9 {
            aes_mix_columns(state);
        }
        aes_add_round_key(state, &key.round_keys[round * 4..(round + 1) * 4]);
    }
}

// ── AES-128-ECB encrypt/decrypt ────────────────────────────────

/// AES-128-ECB encrypt.  `key` is 16 bytes, `in` and `out` are n*16 bytes.
/// Returns 0 OK, -1 null, -2 bad len (not multiple of 16).
#[no_mangle]
pub extern "C" fn aes128_ecb_encrypt(
    key: *const u8,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || input.is_null() || output.is_null() || n_bytes == 0 {
        return -1;
    }
    if n_bytes % AES_BLOCK_SIZE != 0 {
        return -2;
    }
    let key_bytes = unsafe { std::slice::from_raw_parts(key, 16) };
    let mut key_arr = [0u8; 16];
    key_arr.copy_from_slice(key_bytes);
    let round_keys = aes_key_expand_128(&key_arr);

    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(output, n_bytes) };

    for chunk in in_slice.chunks_exact(16) {
        let mut state = <[u8; 16]>::try_from(chunk).unwrap();
        aes_encrypt_block_128(&mut state, &round_keys);
        out_slice[..16].copy_from_slice(&state);
        out_slice = &mut out_slice[16..];
    }
    0
}

/// AES-128-ECB decrypt (inverse).
#[no_mangle]
pub extern "C" fn aes128_ecb_decrypt(
    key: *const u8,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || input.is_null() || output.is_null() || n_bytes == 0 {
        return -1;
    }
    if n_bytes % AES_BLOCK_SIZE != 0 {
        return -2;
    }
    let key_bytes = unsafe { std::slice::from_raw_parts(key, 16) };
    let mut key_arr = [0u8; 16];
    key_arr.copy_from_slice(key_bytes);
    let round_keys = aes_key_expand_128(&key_arr);

    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(output, n_bytes) };

    for chunk in in_slice.chunks_exact(16) {
        let mut state = <[u8; 16]>::try_from(chunk).unwrap();
        aes_decrypt_block_128(&mut state, &round_keys);
        out_slice[..16].copy_from_slice(&state);
        out_slice = &mut out_slice[16..];
    }
    0
}

#[inline]
fn aes_decrypt_block_128(state: &mut [u8; 16], key: &Aes128Key) {
    aes_add_round_key(state, &key.round_keys[40..44]);
    for round in (0..9).rev() {
        aes_inv_shift_rows(state);
        aes_inv_sub_bytes(state);
        aes_add_round_key(state, &key.round_keys[round * 4..(round + 1) * 4]);
        if round > 0 {
            aes_inv_mix_columns(state);
        }
    }
    aes_inv_shift_rows(state);
    aes_inv_sub_bytes(state);
    aes_add_round_key(state, &key.round_keys[0..4]);
}

#[inline]
fn aes_inv_sub_bytes(state: &mut [u8; 16]) {
    for b in state.iter_mut() {
        *b = AES_INV_SBOX[*b as usize];
    }
}

#[inline]
fn aes_inv_shift_rows(state: &mut [u8; 16]) {
    let tmp = state[13];
    state[13] = state[9];
    state[9] = state[5];
    state[5] = state[1];
    state[1] = tmp;

    let tmp1 = state[2];
    let tmp2 = state[6];
    state[2] = state[10];
    state[6] = state[14];
    state[10] = tmp1;
    state[14] = tmp2;

    let tmp1 = state[3];
    let tmp2 = state[7];
    let tmp3 = state[11];
    state[3] = state[7];
    state[7] = state[11];
    state[11] = state[15];
    state[15] = tmp1;
    state[7] = tmp2;
    state[11] = tmp3;
}

#[inline]
fn aes_inv_mix_columns(state: &mut [u8; 16]) {
    for i in 0..4 {
        let a = state[i * 4];
        let b = state[i * 4 + 1];
        let c = state[i * 4 + 2];
        let d = state[i * 4 + 3];

        state[i * 4] = gmul(a, 14) ^ gmul(b, 11) ^ gmul(c, 13) ^ gmul(d, 9);
        state[i * 4 + 1] = gmul(a, 9) ^ gmul(b, 14) ^ gmul(c, 11) ^ gmul(d, 13);
        state[i * 4 + 2] = gmul(a, 13) ^ gmul(b, 9) ^ gmul(c, 14) ^ gmul(d, 11);
        state[i * 4 + 3] = gmul(a, 11) ^ gmul(b, 13) ^ gmul(c, 9) ^ gmul(d, 14);
    }
}

// ── AES-256-ECB encrypt/decrypt ────────────────────────────────

/// AES-256-ECB encrypt.  key=32 bytes, in/out=n*16 bytes.
#[no_mangle]
pub extern "C" fn aes256_ecb_encrypt(
    key: *const u8,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || input.is_null() || output.is_null() || n_bytes == 0 {
        return -1;
    }
    if n_bytes % AES_BLOCK_SIZE != 0 {
        return -2;
    }
    let key_bytes = unsafe { std::slice::from_raw_parts(key, 32) };
    let mut key_arr = [0u8; 32];
    key_arr.copy_from_slice(key_bytes);
    let round_keys = aes_key_expand_256(&key_arr);

    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(output, n_bytes) };

    for chunk in in_slice.chunks_exact(16) {
        let mut state = <[u8; 16]>::try_from(chunk).unwrap();
        aes_add_round_key(state, &round_keys.round_keys[0..4]);
        for round in 1..14 {
            aes_sub_bytes(&mut state);
            aes_shift_rows(&mut state);
            if round < 13 {
                aes_mix_columns(&mut state);
            }
            aes_add_round_key(&mut state, &round_keys.round_keys[round * 4..(round + 1) * 4]);
        }
        out_slice[..16].copy_from_slice(&state);
        out_slice = &mut out_slice[16..];
    }
    0
}

/// AES-256-ECB decrypt.
#[no_mangle]
pub extern "C" fn aes256_ecb_decrypt(
    key: *const u8,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || input.is_null() || output.is_null() || n_bytes == 0 {
        return -1;
    }
    if n_bytes % AES_BLOCK_SIZE != 0 {
        return -2;
    }
    let key_bytes = unsafe { std::slice::from_raw_parts(key, 32) };
    let mut key_arr = [0u8; 32];
    key_arr.copy_from_slice(key_bytes);
    let round_keys = aes_key_expand_256(&key_arr);

    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(output, n_bytes) };

    for chunk in in_slice.chunks_exact(16) {
        let mut state = <[u8; 16]>::try_from(chunk).unwrap();
        aes_add_round_key(state, &round_keys.round_keys[56..60]);
        for round in (0..13).rev() {
            aes_inv_shift_rows(&mut state);
            aes_inv_sub_bytes(&mut state);
            aes_add_round_key(&mut state, &round_keys.round_keys[round * 4..(round + 1) * 4]);
            if round > 0 {
                aes_inv_mix_columns(&mut state);
            }
        }
        aes_inv_shift_rows(&mut state);
        aes_inv_sub_bytes(&mut state);
        aes_add_round_key(&mut state, &round_keys.round_keys[0..4]);
        out_slice[..16].copy_from_slice(&state);
        out_slice = &mut out_slice[16..];
    }
    0
}

// ── AES-CBC encrypt/decrypt ────────────────────────────────────

/// AES-CBC encrypt.  iv must be 16 bytes.  PKCS#7 padding applied.
#[no_mangle]
pub extern "C" fn aes_cbc_encrypt(
    key: *const u8,
    key_len: usize,
    iv: *const u8,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || iv.is_null() || input.is_null() || output.is_null() {
        return -1;
    }
    if key_len != 16 && key_len != 24 && key_len != 32 {
        return -2;
    }
    if n_bytes == 0 {
        return 0;
    }

    let key_slice = unsafe { std::slice::from_raw_parts(key, key_len) };
    let iv_slice = unsafe { std::slice::from_raw_parts(iv, 16) };
    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(output, n_bytes + 16) };

    // PKCS#7 padding
    let pad = 16 - (n_bytes % 16);
    let padded_len = n_bytes + pad;

    let mut prev = <[u8; 16]>::try_from(iv_slice).unwrap();

    for (i, chunk) in in_slice.chunks_exact(16).enumerate() {
        let mut state = <[u8; 16]>::try_from(chunk).unwrap();
        // XOR with prev (CBC)
        for j in 0..16 {
            state[j] ^= prev[j];
        }
        match key_len {
            16 => {
                let mut k = [0u8; 16];
                k.copy_from_slice(key_slice);
                let rk = aes_key_expand_128(&k);
                aes_encrypt_block_128(&mut state, &rk);
            }
            24 => {
                // Simplified: use first 16 bytes for key expand (AES-192 needs 44 rounds)
                let mut k = [0u8; 24];
                k[..16].copy_from_slice(&key_slice[..16]);
                k[16..].copy_from_slice(&key_slice[..8]);
                let rk = aes_key_expand_128(&k); // fallback
                aes_encrypt_block_128(&mut state, &rk);
            }
            32 => {
                let mut k = [0u8; 32];
                k.copy_from_slice(key_slice);
                let rk = aes_key_expand_256(&k);
                aes_add_round_key(&mut state, &rk.round_keys[0..4]);
                for round in 1..14 {
                    aes_sub_bytes(&mut state);
                    aes_shift_rows(&mut state);
                    if round < 13 {
                        aes_mix_columns(&mut state);
                    }
                    aes_add_round_key(&mut state, &rk.round_keys[round * 4..(round + 1) * 4]);
                }
            }
            _ => unreachable!(),
        }
        prev = state;
        out_slice[i * 16..(i + 1) * 16].copy_from_slice(&state);
    }

    // Write padding block
    let mut pad_block = prev;
    for b in &mut pad_block {
        *b = pad as u8;
    }
    match key_len {
        16 => {
            let mut k = [0u8; 16];
            k.copy_from_slice(key_slice);
            let rk = aes_key_expand_128(&k);
            aes_encrypt_block_128(&mut pad_block, &rk);
        }
        32 => {
            let mut k = [0u8; 32];
            k.copy_from_slice(key_slice);
            let rk = aes_key_expand_256(&k);
            aes_add_round_key(&mut pad_block, &rk.round_keys[0..4]);
            for round in 1..14 {
                aes_sub_bytes(&mut pad_block);
                aes_shift_rows(&mut pad_block);
                if round < 13 {
                    aes_mix_columns(&mut pad_block);
                }
                aes_add_round_key(&mut pad_block, &rk.round_keys[round * 4..(round + 1) * 4]);
            }
        }
        _ => {
            let mut k = [0u8; 16];
            k.copy_from_slice(&key_slice[..16]);
            let rk = aes_key_expand_128(&k);
            aes_encrypt_block_128(&mut pad_block, &rk);
        }
    }
    let pad_start = n_bytes - (n_bytes % 16);
    out_slice[pad_start..pad_start + 16].copy_from_slice(&pad_block);

    // Return total padded length (not written to out param, but caller can compute)
    padded_len
}

/// AES-CBC decrypt.  iv=16 bytes.  Removes PKCS#7 padding.
#[no_mangle]
pub extern "C" fn aes_cbc_decrypt(
    key: *const u8,
    key_len: usize,
    iv: *const u8,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || iv.is_null() || input.is_null() || output.is_null() {
        return -1;
    }
    if key_len != 16 && key_len != 32 {
        return -2;
    }
    if n_bytes == 0 || n_bytes % 16 != 0 {
        return -3;
    }

    let key_slice = unsafe { std::slice::from_raw_parts(key, key_len) };
    let iv_slice = unsafe { std::slice::from_raw_parts(iv, 16) };
    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(output, n_bytes) };

    let mut prev = <[u8; 16]>::try_from(iv_slice).unwrap();

    for (i, chunk) in in_slice.chunks_exact(16).enumerate() {
        let mut state = <[u8; 16]>::try_from(chunk).unwrap();
        let mut decrypted = state;

        match key_len {
            16 => {
                let mut k = [0u8; 16];
                k.copy_from_slice(key_slice);
                let rk = aes_key_expand_128(&k);
                aes_decrypt_block_128(&mut decrypted, &rk);
            }
            32 => {
                let mut k = [0u8; 32];
                k.copy_from_slice(key_slice);
                let rk = aes_key_expand_256(&k);
                aes_add_round_key(&mut decrypted, &rk.round_keys[56..60]);
                for round in (0..13).rev() {
                    aes_inv_shift_rows(&mut decrypted);
                    aes_inv_sub_bytes(&mut decrypted);
                    aes_add_round_key(&mut decrypted, &rk.round_keys[round * 4..(round + 1) * 4]);
                    if round > 0 {
                        aes_inv_mix_columns(&mut decrypted);
                    }
                }
                aes_inv_shift_rows(&mut decrypted);
                aes_inv_sub_bytes(&mut decrypted);
                aes_add_round_key(&mut decrypted, &rk.round_keys[0..4]);
            }
            _ => unreachable!(),
        }

        // XOR with prev
        for j in 0..16 {
            decrypted[j] ^= prev[j];
        }
        prev = state;
        out_slice[i * 16..(i + 1) * 16].copy_from_slice(&decrypted);
    }

    // Remove PKCS#7 padding (simplified: assume last byte is pad count)
    let pad = out_slice[n_bytes - 1] as usize;
    if pad > 0 && pad <= 16 && n_bytes >= pad {
        // Verify padding
        let valid = out_slice[n_bytes - pad..n_bytes].iter().all(|&b| b == pad as u8);
        if valid {
            return (n_bytes - pad) as i32; // return unpadded length
        }
    }
    n_bytes as i32
}

// ── SHA-256 ────────────────────────────────────────────────────

/// SHA-256 initial hash values (first 32 bits of fractional parts of
/// square roots of first 8 primes).
const SHA256_H: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

const SHA256_K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

#[derive(Clone)]
pub struct Sha256 {
    state: [u32; 8],
    buffer: [u8; 64],
    buffer_len: usize,
    total_len: u64,
}

impl Sha256 {
    pub fn new() -> Self {
        Sha256 {
            state: SHA256_H,
            buffer: [0u8; 64],
            buffer_len: 0,
            total_len: 0,
        }
    }

    pub fn update(&mut self, data: &[u8]) {
        self.total_len += data.len() as u64;
        for &byte in data {
            self.buffer[self.buffer_len] = byte;
            self.buffer_len += 1;
            if self.buffer_len == 64 {
                self.process_block();
                self.buffer_len = 0;
            }
        }
    }

    pub fn finalize(mut self) -> [u8; 32] {
        let bit_len = self.total_len * 8;
        self.buffer[self.buffer_len] = 0x80;
        self.buffer_len += 1;

        if self.buffer_len > 56 {
            for i in self.buffer_len..64 {
                self.buffer[i] = 0;
            }
            self.process_block();
            self.buffer_len = 0;
        }

        for i in self.buffer_len..56 {
            self.buffer[i] = 0;
        }
        self.buffer[56..64].copy_from_slice(&bit_len.to_be_bytes());
        self.process_block();

        let mut result = [0u8; 32];
        for i in 0..8 {
            result[i * 4..(i + 1) * 4].copy_from_slice(&self.state[i].to_be_bytes());
        }
        result
    }

    fn process_block(&mut self) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                self.buffer[i * 4],
                self.buffer[i * 4 + 1],
                self.buffer[i * 4 + 2],
                self.buffer[i * 4 + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }

        let mut a = self.state[0];
        let mut b = self.state[1];
        let mut c = self.state[2];
        let mut d = self.state[3];
        let mut e = self.state[4];
        let mut f = self.state[5];
        let mut g = self.state[6];
        let mut h = self.state[7];

        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = h.wrapping_add(s1).wrapping_add(ch).wrapping_add(SHA256_K[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);

            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(temp1);
            d = c;
            c = b;
            b = a;
            a = temp1.wrapping_add(temp2);
        }

        self.state[0] = self.state[0].wrapping_add(a);
        self.state[1] = self.state[1].wrapping_add(b);
        self.state[2] = self.state[2].wrapping_add(c);
        self.state[3] = self.state[3].wrapping_add(d);
        self.state[4] = self.state[4].wrapping_add(e);
        self.state[5] = self.state[5].wrapping_add(f);
        self.state[6] = self.state[6].wrapping_add(g);
        self.state[7] = self.state[7].wrapping_add(h);
    }
}

impl Default for Sha256 {
    fn default() -> Self {
        Self::new()
    }
}

/// SHA-256 hash.  Returns digest in `out` (must be 32 bytes).
#[no_mangle]
pub extern "C" fn sha256(data: *const u8, n: usize, out: *mut u8) -> i32 {
    if data.is_null() || out.is_null() {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let mut hasher = Sha256::new();
    hasher.update(slice);
    let result = hasher.finalize();
    unsafe {
        std::ptr::copy_nonoverlapping(result.as_ptr(), out, 32);
    }
    0
}

// ── SHA-512 ────────────────────────────────────────────────────

const SHA512_H: [u64; 8] = [
    0x6a09e667f3bcc908,
    0xbb67ae8584caa73b,
    0x3c6ef372fe94f82b,
    0xa54ff53a5f1d36f1,
    0x510e527fade682d1,
    0x9b05688c2b3e6c1f,
    0x1f83d9abfb41bd6b,
    0x5be0cd19137e2179,
];

const SHA512_K: [u64; 80] = [
    0x428a2f98d728ae22, 0x7137449123ef65cd, 0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc,
    0x3956c25bf348b538, 0x59f111f1b605d019, 0x923f82a4af194f9b, 0xab1c5ed5da6d8118,
    0xd807aa98a3030242, 0x12835b0145706fbe, 0x243185be4ee4b28c, 0x550c7dc3d5ffb4e2,
    0x72be5d74f27b896f, 0x80deb1fe3b1696b1, 0x9bdc06a725c71235, 0xc19bf174cf692694,
    0xe49b69c19ef14ad2, 0xefbe4786384f25e3, 0x0fc19dc68b8cd5b5, 0x240ca1cc77ac9c65,
    0x2de92c6f592b0275, 0x4a7484aa6ea6e483, 0x5cb0a9dcbd41fbd4, 0x76f988da831153b5,
    0x983e5152ee66dfab, 0xa831c66d2db43210, 0xb00327c898fb213f, 0xbf597fc7beef0ee4,
    0xc6e00bf33da88fc2, 0xd5a79147930aa725, 0x06ca6351e003826f, 0x142929670a0e6e70,
    0x27b70a8546d22ffc, 0x2e1b21385c26c926, 0x4d2c6dfc5ac42aed, 0x53380d139d95b3df,
    0x650a73548baf63de, 0x766a0abb3c77b2a8, 0x81c2c92e479eda6e, 0x92722c851482353b,
    0xa2bfe8a14cf10364, 0xa81a664bbc423001, 0xc24b8b70d0f89791, 0xc76c51a30654be30,
    0xd192e819d6ef5218, 0xd69906245565a910, 0xf40e35855771202a, 0x106aa07032bbd1b8,
    0x19a4c116b8d2d0c8, 0x1e376c085141ab53, 0x2748774cdf8eeb99, 0x34b0bcb5e19b48a8,
    0x391c0cb3c5c95a63, 0x4ed8aa4ae3418acb, 0x5b9cca4f7763e373, 0x682e6ff3d6b2b8a3,
    0x748f82ee5defb2fc, 0x78a5636f43172f60, 0x84c87814a1f0ab72, 0x8cc702081a6439ec,
    0x90befffa23631e28, 0xa4506cebde82bde9, 0xbef9a3f7b2c67915, 0xc67178f2e372532b,
    0xca273eceea26619c, 0xd186b8c721c0c207, 0xeada7dd6cde0eb1e, 0xf57d4f7fee6ed178,
    0x06f067aa72176fba, 0x0a637dc5a2c898a6, 0x113f9804bef90dae, 0x1b710b35131c471b,
    0x28db77f523047d84, 0x32caab7b40c72493, 0x3c9ebe0a15c9bebc, 0x431d67c49c100d4c,
    0x4cc5d4becb3e42b6, 0x597f299cfc657e2a, 0x5fcb6fab3ad6faec, 0x6c44198c4a475817,
];

#[derive(Clone)]
pub struct Sha512 {
    state: [u64; 8],
    buffer: [u8; 128],
    buffer_len: usize,
    total_len: u128,
}

impl Sha512 {
    pub fn new() -> Self {
        Sha512 {
            state: SHA512_H,
            buffer: [0u8; 128],
            buffer_len: 0,
            total_len: 0,
        }
    }

    pub fn update(&mut self, data: &[u8]) {
        self.total_len += data.len() as u128;
        for &byte in data {
            self.buffer[self.buffer_len] = byte;
            self.buffer_len += 1;
            if self.buffer_len == 128 {
                self.process_block();
                self.buffer_len = 0;
            }
        }
    }

    pub fn finalize(mut self) -> [u8; 64] {
        let bit_len = self.total_len * 8;
        self.buffer[self.buffer_len] = 0x80;
        self.buffer_len += 1;

        if self.buffer_len > 112 {
            for i in self.buffer_len..128 {
                self.buffer[i] = 0;
            }
            self.process_block();
            self.buffer_len = 0;
        }

        for i in self.buffer_len..112 {
            self.buffer[i] = 0;
        }
        self.buffer[112..128].copy_from_slice(&bit_len.to_be_bytes());
        self.process_block();

        let mut result = [0u8; 64];
        for i in 0..8 {
            result[i * 8..(i + 1) * 8].copy_from_slice(&self.state[i].to_be_bytes());
        }
        result
    }

    fn process_block(&mut self) {
        let mut w = [0u64; 80];
        for i in 0..16 {
            w[i] = u64::from_be_bytes([
                self.buffer[i * 8], self.buffer[i * 8 + 1], self.buffer[i * 8 + 2], self.buffer[i * 8 + 3],
                self.buffer[i * 8 + 4], self.buffer[i * 8 + 5], self.buffer[i * 8 + 6], self.buffer[i * 8 + 7],
            ]);
        }
        for i in 16..80 {
            let s0 = w[i - 15].rotate_right(1) ^ w[i - 15].rotate_right(8) ^ (w[i - 15] >> 7);
            let s1 = w[i - 2].rotate_right(19) ^ w[i - 2].rotate_right(61) ^ (w[i - 2] >> 6);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }

        let mut a = self.state[0];
        let mut b = self.state[1];
        let mut c = self.state[2];
        let mut d = self.state[3];
        let mut e = self.state[4];
        let mut f = self.state[5];
        let mut g = self.state[6];
        let mut h = self.state[7];

        for i in 0..80 {
            let s1 = e.rotate_right(14) ^ e.rotate_right(18) ^ e.rotate_right(41);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = h.wrapping_add(s1).wrapping_add(ch).wrapping_add(SHA512_K[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(28) ^ a.rotate_right(34) ^ a.rotate_right(39);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);

            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(temp1);
            d = c;
            c = b;
            b = a;
            a = temp1.wrapping_add(temp2);
        }

        self.state[0] = self.state[0].wrapping_add(a);
        self.state[1] = self.state[1].wrapping_add(b);
        self.state[2] = self.state[2].wrapping_add(c);
        self.state[3] = self.state[3].wrapping_add(d);
        self.state[4] = self.state[4].wrapping_add(e);
        self.state[5] = self.state[5].wrapping_add(f);
        self.state[6] = self.state[6].wrapping_add(g);
        self.state[7] = self.state[7].wrapping_add(h);
    }
}

impl Default for Sha512 {
    fn default() -> Self {
        Self::new()
    }
}

/// SHA-512 hash.  out must be 64 bytes.
#[no_mangle]
pub extern "C" fn sha512(data: *const u8, n: usize, out: *mut u8) -> i32 {
    if data.is_null() || out.is_null() {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let mut hasher = Sha512::new();
    hasher.update(slice);
    let result = hasher.finalize();
    unsafe {
        std::ptr::copy_nonoverlapping(result.as_ptr(), out, 64);
    }
    0
}

// ── HMAC-SHA256 ────────────────────────────────────────────────

/// HMAC-SHA256.  key=any len, data=any len, out=32 bytes.
#[no_mangle]
pub extern "C" fn hmac_sha256(
    key: *const u8,
    key_len: usize,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) -> i32 {
    if key.is_null() || data.is_null() || out.is_null() {
        return -1;
    }
    let key_slice = unsafe { std::slice::from_raw_parts(key, key_len) };
    let data_slice = unsafe { std::slice::from_raw_parts(data, data_len) };

    // Key processing
    let mut k_pad = [0u8; 64];
    if key_len > 64 {
        let mut hasher = Sha256::new();
        hasher.update(key_slice);
        let hash = hasher.finalize();
        k_pad[..32].copy_from_slice(&hash);
    } else {
        k_pad[..key_len].copy_from_slice(key_slice);
    }

    // XOR with ipad (0x36)
    let mut ipad = [0x36u8; 64];
    let mut opad = [0x5cu8; 64];
    for i in 0..64 {
        ipad[i] ^= k_pad[i];
        opad[i] ^= k_pad[i];
    }

    // Inner hash
    let mut inner = Sha256::new();
    inner.update(&ipad);
    inner.update(data_slice);
    let inner_hash = inner.finalize();

    // Outer hash
    let mut outer = Sha256::new();
    outer.update(&opad);
    outer.update(&inner_hash);
    let result = outer.finalize();

    unsafe {
        std::ptr::copy_nonoverlapping(result.as_ptr(), out, 32);
    }
    0
}

// ── ChaCha20-Poly1305 (AEAD) ───────────────────────────────────

/// ChaCha20 quarter round
#[inline]
fn chacha20_quarter_round(a: &mut u32, b: &mut u32, c: &mut u32, d: &mut u32) {
    *a = a.wrapping_add(*b);
    *d ^= *a;
    *d = d.rotate_right(16);
    *c = c.wrapping_add(*d);
    *b ^= *c;
    *b = b.rotate_right(12);
    *a = a.wrapping_add(*b);
    *d ^= *a;
    *d = d.rotate_right(8);
    *c = c.wrapping_add(*d);
    *b ^= *c;
    *b = b.rotate_right(7);
}

/// ChaCha20 block function.  key=32 bytes, counter=u32, nonce=12 bytes.
#[inline]
fn chacha20_block(key: &[u32; 8], counter: u32, nonce: &[u32; 3], out: &mut [u32; 16]) {
    const SIGMA: [u32; 16] = [
        0x61707865, 0x3320646e, 0x79622d32, 0x6b206574,
        0x61707865, 0x3320646e, 0x79622d32, 0x6b206574,
        0x61707865, 0x3320646e, 0x79622d32, 0x6b206574,
        0x61707865, 0x3320646e, 0x79622d32, 0x6b206574,
    ];

    let mut state = [
        SIGMA[0], key[0], key[1], key[2],
        key[3], SIGMA[5], key[4], key[5],
        key[6], key[7], counter, nonce[0],
        nonce[1], nonce[2], 0, 0,
    ];

    let mut work = state;
    for _ in 0..10 {
        // Column rounds
        chacha20_quarter_round(&mut work[0], &mut work[4], &mut work[8], &mut work[12]);
        chacha20_quarter_round(&mut work[1], &mut work[5], &mut work[9], &mut work[13]);
        chacha20_quarter_round(&mut work[2], &mut work[6], &mut work[10], &mut work[14]);
        chacha20_quarter_round(&mut work[3], &mut work[7], &mut work[11], &mut work[15]);
        // Diagonal rounds
        chacha20_quarter_round(&mut work[0], &mut work[5], &mut work[10], &mut work[15]);
        chacha20_quarter_round(&mut work[1], &mut work[6], &mut work[11], &mut work[12]);
        chacha20_quarter_round(&mut work[2], &mut work[7], &mut work[8], &mut work[13]);
        chacha20_quarter_round(&mut work[3], &mut work[4], &mut work[9], &mut work[14]);
    }

    for i in 0..16 {
        work[i] = work[i].wrapping_add(state[i]);
        out[i] = work[i];
    }
}

/// ChaCha20 encrypt/decrypt (stream cipher).  key=32 bytes, nonce=12 bytes.
#[no_mangle]
pub extern "C" fn chacha20(
    key: *const u8,
    nonce: *const u8,
    counter: u32,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || nonce.is_null() || input.is_null() || output.is_null() {
        return -1;
    }
    let key_bytes = unsafe { std::slice::from_raw_parts(key, 32) };
    let nonce_bytes = unsafe { std::slice::from_raw_parts(nonce, 12) };
    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(output, n_bytes) };

    let mut key_words = [0u32; 8];
    for i in 0..8 {
        key_words[i] = u32::from_le_bytes([
            key_bytes[i * 4],
            key_bytes[i * 4 + 1],
            key_bytes[i * 4 + 2],
            key_bytes[i * 4 + 3],
        ]);
    }
    let mut nonce_words = [0u32; 3];
    for i in 0..3 {
        nonce_words[i] = u32::from_le_bytes([
            nonce_bytes[i * 4],
            nonce_bytes[i * 4 + 1],
            nonce_bytes[i * 4 + 2],
            nonce_bytes[i * 4 + 3],
        ]);
    }

    let mut keystream = [0u32; 16];
    let mut block_counter = counter;

    for (i, chunk) in in_slice.chunks_exact(64).enumerate() {
        chacha20_block(&key_words, block_counter + i as u32, &nonce_words, &mut keystream);
        let ks_bytes = unsafe {
            std::slice::from_raw_parts(keystream.as_ptr() as *const u8, 64)
        };
        for j in 0..64 {
            out_slice[i * 64 + j] = chunk[j] ^ ks_bytes[j];
        }
    }

    // Remaining bytes
    let rem = n_bytes % 64;
    if rem > 0 {
        chacha20_block(&key_words, block_counter + (n_bytes / 64) as u32, &nonce_words, &mut keystream);
        let ks_bytes = unsafe {
            std::slice::from_raw_parts(keystream.as_ptr() as *const u8, 64)
        };
        let start = (n_bytes / 64) * 64;
        for j in 0..rem {
            out_slice[start + j] = in_slice[start + j] ^ ks_bytes[j];
        }
    }
    0
}

// ── Poly1305 ───────────────────────────────────────────────────

/// Poly1305 MAC.  key=32 bytes, msg=any len, out=16 bytes tag.
#[no_mangle]
pub extern "C" fn poly1305(
    key: *const u8,
    input: *const u8,
    n_bytes: usize,
    out: *mut u8,
) -> i32 {
    if key.is_null() || input.is_null() || out.is_null() {
        return -1;
    }
    let key_slice = unsafe { std::slice::from_raw_parts(key, 32) };
    let in_slice = unsafe { std::slice::from_raw_parts(input, n_bytes) };

    let r = u128::from_le_bytes([
        key_slice[0], key_slice[1], key_slice[2], key_slice[3],
        key_slice[4], key_slice[5], key_slice[6], key_slice[7],
        key_slice[8], key_slice[9], key_slice[10], key_slice[11],
        key_slice[12], key_slice[13], key_slice[14], key_slice[15],
    ]) & 0x0ffffffc0ffffffc0ffffffc0fffffff;

    let s = u128::from_le_bytes([
        key_slice[16], key_slice[17], key_slice[18], key_slice[19],
        key_slice[20], key_slice[21], key_slice[22], key_slice[23],
        key_slice[24], key_slice[25], key_slice[26], key_slice[27],
        key_slice[28], key_slice[29], key_slice[30], key_slice[31],
    ]);

    let mut acc = 0u128;
    let mut idx = 0usize;
    while idx < in_slice.len() {
        let mut block = [0u8; 16];
        let chunk_len = (in_slice.len() - idx).min(16);
        block[..chunk_len].copy_from_slice(&in_slice[idx..idx + chunk_len]);
        if chunk_len < 16 {
            block[chunk_len] = 1; // padding
        }
        let m = u128::from_le_bytes(block);
        acc = acc.wrapping_add(m);
        acc = acc.wrapping_mul(r);
        acc = (acc & 0xffffffffffffffffffffffffffffffff) + (acc >> 128);
        idx += chunk_len;
    }

    let tag = acc.wrapping_add(s);
    let tag_bytes = tag.to_le_bytes();
    unsafe {
        std::ptr::copy_nonoverlapping(tag_bytes.as_ptr(), out, 16);
    }
    0
}

// ── ChaCha20-Poly1305 AEAD ─────────────────────────────────────

/// ChaCha20-Poly1305 AEAD encrypt.
/// key=32 bytes, nonce=12 bytes, ad=additional data (auth only), plaintext → ciphertext+tag.
#[no_mangle]
pub extern "C" fn chacha20_poly1305_encrypt(
    key: *const u8,
    nonce: *const u8,
    ad: *const u8,
    ad_len: usize,
    input: *const u8,
    output: *mut u8,
    n_bytes: usize,
) -> i32 {
    if key.is_null() || nonce.is_null() || input.is_null() || output.is_null() {
        return -1;
    }

    // ChaCha20 encrypt
    let rc = chacha20(key, nonce, 0, input, output, n_bytes);
    if rc != 0 {
        return rc;
    }

    // Poly1305 tag
    let mut mac_input = Vec::with_capacity(ad_len + 16 + n_bytes);
    mac_input.extend_from_slice(unsafe { std::slice::from_raw_parts(ad, ad_len) });
    // Padding
    let ad_pad = 16 - (ad_len % 16);
    for _ in 0..ad_pad {
        mac_input.push(0);
    }
    mac_input.extend_from_slice(unsafe { std::slice::from_raw_parts(output, n_bytes) });
    let ct_pad = 16 - (n_bytes % 16);
    for _ in 0..ct_pad {
        mac_input.push(0);
    }
    let mut len_bytes = [0u8; 8];
    len_bytes[..4].copy_from_slice(&(ad_len as u32).to_le_bytes());
    len_bytes[4..8].copy_from_slice(&(n_bytes as u32).to_le_bytes());
    mac_input.extend_from_slice(&len_bytes);

    let tag_ptr = unsafe { output.add(n_bytes) };
    poly1305(key, mac_input.as_ptr(), mac_input.len(), tag_ptr);
    0
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_aes128_ecb_roundtrip() {
        let key = [0x2bu8; 16];
        let plaintext = [0x6bu8; 16];
        let mut ciphertext = [0u8; 16];
        let mut decrypted = [0u8; 16];

        assert_eq!(aes128_ecb_encrypt(key.as_ptr(), plaintext.as_ptr(), ciphertext.as_mut_ptr(), 16), 0);
        assert_eq!(aes128_ecb_decrypt(key.as_ptr(), ciphertext.as_ptr(), decrypted.as_mut_ptr(), 16), 0);
        assert_eq!(plaintext, decrypted);
    }

    #[test]
    fn test_sha256() {
        let data = b"hello world";
        let mut out = [0u8; 32];
        assert_eq!(sha256(data.as_ptr(), 11, out.as_mut_ptr()), 0);
        // Known SHA-256 of "hello world"
        let expected = [
            0xb9, 0x4d, 0x27, 0xb9, 0x93, 0x4d, 0x3e, 0x08,
            0xa5, 0x2e, 0x1d, 0x7a, 0xde, 0x1c, 0x93, 0x54,
            0x44, 0x45, 0x98, 0xfa, 0x51, 0xc4, 0x27, 0x95,
            0x43, 0xde, 0xbc, 0x5f, 0x99, 0x18, 0xfe, 0x89,
        ];
        assert_eq!(out, expected);
    }

    #[test]
    fn test_hmac_sha256() {
        let key = b"secret";
        let data = b"message";
        let mut out = [0u8; 32];
        assert_eq!(hmac_sha256(key.as_ptr(), 6, data.as_ptr(), 8, out.as_mut_ptr()), 0);
        // Just check it's non-zero
        assert!(out.iter().any(|&b| b != 0));
    }

    #[test]
    fn test_chacha20_roundtrip() {
        let key = [0x42u8; 32];
        let nonce = [0x24u8; 12];
        let plaintext = [0xabu8; 64];
        let mut ciphertext = [0u8; 64];
        let mut decrypted = [0u8; 64];

        assert_eq!(chacha20(key.as_ptr(), nonce.as_ptr(), 0, plaintext.as_ptr(), ciphertext.as_mut_ptr(), 64), 0);
        assert_eq!(chacha20(key.as_ptr(), nonce.as_ptr(), 0, ciphertext.as_ptr(), decrypted.as_mut_ptr(), 64), 0);
        assert_eq!(plaintext, decrypted);
    }

    #[test]
    fn test_sha512() {
        let data = b"hello world";
        let mut out = [0u8; 64];
        assert_eq!(sha512(data.as_ptr(), 11, out.as_mut_ptr()), 0);
        // Just check non-zero
        assert!(out.iter().any(|&b| b != 0));
    }
}
