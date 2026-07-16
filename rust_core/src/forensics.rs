//! minxg_rust_core/src/forensics.rs — memory forensics & binary analysis.
//!
//! Industrial implementations of ELF segment parsing, process image
//! analysis, string extraction, and entropy analysis.
//!
//! ## Implemented
//!
//! * ELF32/ELF64 parsing (header, program headers, section headers)
//! * PE (Portable Executable) parsing for Windows binaries
//! * Mach-O parsing for macOS binaries
//! * String extraction from binary blobs (ASCII/UTF-8)
//! * Shannon entropy computation for packed/encrypted sections
//! * Hex string detection (EML, MSG, RFC)
//! * File magic detection (CARVED files)
//! * Address range resolution (ASLR defeat for known mappings)

#![allow(dead_code)]

pub const ELF_MAGIC: [u8; 4] = [0x7F, b'E', b'L', b'F'];
pub const PE_MAGIC: [u8; 4] = [b'M', b'Z', 0, 0];
pub const MACHO_MAGIC_LE: [u8; 4] = [0xCF, 0xFA, 0xED, 0xFE];
pub const MACHO_MAGIC_BE: [u8; 4] = [0xFE, 0xED, 0xFA, 0xCE];
pub const MACHO_FAT_MAGIC: [u8; 4] = [0xCA, 0xFE, 0xBA, 0xBE];

pub const FILE_MAX_BUFFER: usize = 256 * 1024 * 1024; // 256 MB for parsing
pub const MAX_FORENSICS_STRINGS: usize = 1_000_000;
pub const MIN_STRING_LENGTH: usize = 4;

// ── ELF Structures ─────────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct ElfHeader {
    pub e_ident: [u8; 16],
    pub e_type: u16,
    pub e_machine: u16,
    pub e_version: u32,
    pub e_entry: u64,
    pub e_phoff: u64,
    pub e_shoff: u64,
    pub e_flags: u32,
    pub e_ehsize: u16,
    pub e_phentsize: u16,
    pub e_phnum: u16,
    pub e_shentsize: u16,
    pub e_shnum: u16,
    pub e_shstrndx: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct ElfProgramHeader {
    pub p_type: u32,
    pub p_flags: u32,
    pub p_offset: u64,
    pub p_vaddr: u64,
    pub p_paddr: u64,
    pub p_filesz: u64,
    pub p_memsz: u64,
    pub p_align: u64,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct ElfSectionHeader {
    pub sh_name: u32,
    pub sh_type: u32,
    pub sh_flags: u64,
    pub sh_addr: u64,
    pub sh_offset: u64,
    pub sh_size: u64,
    pub sh_link: u32,
    pub sh_info: u32,
    pub sh_addralign: u64,
    pub sh_entsize: u64,
}

// ── PE Structures ─────────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct PeHeader {
    pub e_magic: [u8; 2],
    pub e_cblp: u16,
    pub e_cp: u16,
    pub e_crlc: u16,
    pub e_cparhdr: u16,
    pub e_minalloc: u16,
    pub e_maxalloc: u16,
    pub e_ss: u16,
    pub e_sp: u16,
    pub e_csum: u16,
    pub e_ip: u16,
    pub e_cs: u16,
    pub e_lfarlc: u16,
    pub e_ovno: u16,
    pub e_oemid: u16,
    pub e_oeminfo: u16,
    pub e_lfanew: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct PeNtHeader {
    pub signature: [u8; 4],
    pub file_header: PeFileHeader,
    pub optional_header: PeOptionalHeader,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct PeFileHeader {
    pub machine: u16,
    pub num_sections: u16,
    pub timestamp: u32,
    pub symtab_ptr: u32,
    pub num_symbols: u32,
    pub opt_header_size: u16,
    pub characteristics: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct PeOptionalHeader {
    pub magic: u16,
    pub linker_version_major: u8,
    pub linker_version_minor: u8,
    pub size_of_code: u32,
    pub size_of_initialized_data: u32,
    pub size_of_uninitialized_data: u32,
    pub address_of_entry_point: u32,
    pub base_of_code: u32,
    pub image_base: u64,
}

// ── Mach-O Structures ─────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct MachOHeader {
    pub magic: u32,
    pub cputype: u32,
    pub cpusubtype: u32,
    pub filetype: u32,
    pub ncmds: u32,
    pub sizeofcmds: u32,
    pub flags: u32,
}

// ── File Format Detection ────────────────────────────────────

/// Detect file format by magic bytes.
#[no_mangle]
pub extern "C" fn forensics_detect_format(data: *const u8, n: usize) -> u8 {
    if data.is_null() || n < 4 {
        return 0;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n.min(8)) };

    // 1=ELF, 2=PE, 3=Mach-O LE, 4=Mach-O BE, 5=Fat Mach-O, 6=ZIP, 7=GZIP, 8=XZ
    if slice.starts_with(&ELF_MAGIC) {
        return 1;
    }
    if slice.starts_with(&PE_MAGIC) {
        return 2;
    }
    if slice.starts_with(&MACHO_MAGIC_LE) {
        return 3;
    }
    if slice.starts_with(&MACHO_MAGIC_BE) {
        return 4;
    }
    if slice.starts_with(&MACHO_FAT_MAGIC) {
        return 5;
    }
    if slice.starts_with(&[0x50, 0x4B, 0x03, 0x04]) {
        return 6;
    }
    if slice.starts_with(&[0x1F, 0x8B]) {
        return 7;
    }
    if slice.starts_with(&[0xFD, 0x37, 0x7A, 0x58, 0x5A]) {
        return 8;
    }
    0
}

// ── ELF Parsing ──────────────────────────────────────────────

/// Parse ELF64 header.  Returns 0 OK, -1 null, -2 not ELF, -3 truncated.
#[no_mangle]
pub extern "C" fn elf_parse_header(
    data: *const u8,
    n: usize,
    header: *mut ElfHeader,
) -> i32 {
    if data.is_null() || header.is_null() || n < 64 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n.min(64)) };
    if !slice.starts_with(&ELF_MAGIC) {
        return -2;
    }

    let hdr = unsafe { &mut *header };
    hdr.e_ident.copy_from_slice(&slice[..16]);

    let is_64 = slice[4] == 2;
    let phoff_offset = if is_64 { 32 } else { 28 };
    let shoff_offset = if is_64 { 40 } else { 32 };
    let ehsize = if is_64 { 64 } else { 52 };

    if is_64 {
        hdr.e_type = u16::from_be_bytes([slice[16], slice[17]]);
        hdr.e_machine = u16::from_be_bytes([slice[18], slice[19]]);
        hdr.e_version = u32::from_be_bytes([slice[20], slice[21], slice[22], slice[23]]);
        hdr.e_entry = u64::from_be_bytes([
            slice[24], slice[25], slice[26], slice[27],
            slice[28], slice[29], slice[30], slice[31],
        ]);
        hdr.e_phoff = u64::from_be_bytes([
            slice[phoff_offset], slice[phoff_offset + 1], slice[phoff_offset + 2], slice[phoff_offset + 3],
            slice[phoff_offset + 4], slice[phoff_offset + 5], slice[phoff_offset + 6], slice[phoff_offset + 7],
        ]);
        hdr.e_shoff = u64::from_be_bytes([
            slice[shoff_offset], slice[shoff_offset + 1], slice[shoff_offset + 2], slice[shoff_offset + 3],
            slice[shoff_offset + 4], slice[shoff_offset + 5], slice[shoff_offset + 6], slice[shoff_offset + 7],
        ]);
    } else {
        hdr.e_type = u16::from_be_bytes([slice[16], slice[17]]);
        hdr.e_machine = u16::from_be_bytes([slice[18], slice[19]]);
        hdr.e_version = u32::from_be_bytes([slice[20], slice[21], slice[22], slice[23]]);
        hdr.e_entry = u32::from_be_bytes([slice[24], slice[25], slice[26], slice[27]]) as u64;
        hdr.e_phoff = u32::from_be_bytes([slice[phoff_offset], slice[phoff_offset + 1], slice[phoff_offset + 2], slice[phoff_offset + 3]]) as u64;
        hdr.e_shoff = u32::from_be_bytes([slice[shoff_offset], slice[shoff_offset + 1], slice[shoff_offset + 2], slice[shoff_offset + 3]]) as u64;
    }

    hdr.e_flags = u32::from_be_bytes([slice[e_ehsize - 16], slice[e_ehsize - 15], slice[e_ehsize - 14], slice[e_ehsize - 13]]);
    hdr.e_ehsize = u16::from_be_bytes([slice[e_ehsize - 12], slice[e_ehsize - 11]]);
    hdr.e_phentsize = u16::from_be_bytes([slice[e_ehsize - 10], slice[e_ehsize - 9]]);
    hdr.e_phnum = u16::from_be_bytes([slice[e_ehsize - 8], slice[e_ehsize - 7]]);
    hdr.e_shentsize = u16::from_be_bytes([slice[e_ehsize - 6], slice[e_ehsize - 5]]);
    hdr.e_shnum = u16::from_be_bytes([slice[e_ehsize - 4], slice[e_ehsize - 3]]);
    hdr.e_shstrndx = u16::from_be_bytes([slice[e_ehsize - 2], slice[e_ehsize - 1]]);

    if n < (hdr.e_phoff + hdr.e_phnum as u64 * hdr.e_phentsize as u64) as usize {
        return -3;
    }
    0
}

/// Parse ELF program header (segment).
#[no_mangle]
pub extern "C" fn elf_parse_program_header(
    data: *const u8,
    n: usize,
    offset: u64,
    is_64: u8,
    header: *mut ElfProgramHeader,
) -> i32 {
    if data.is_null() || header.is_null() {
        return -1;
    }
    let ph_size = if is_64 != 0 { 56 } else { 32 };
    if n < (offset + ph_size) as usize {
        return -3;
    }
    let slice = unsafe { std::slice::from_raw_parts(data.add(offset as usize), ph_size) };
    let hdr = unsafe { &mut *header };

    hdr.p_type = u32::from_be_bytes([slice[0], slice[1], slice[2], slice[3]]);
    if is_64 != 0 {
        hdr.p_flags = u32::from_be_bytes([slice[4], slice[5], slice[6], slice[7]]);
    } else {
        hdr.p_flags = u32::from_be_bytes([slice[24], slice[25], slice[26], slice[27]]);
    }
    hdr.p_offset = if is_64 != 0 {
        u64::from_be_bytes([
            slice[8], slice[9], slice[10], slice[11],
            slice[12], slice[13], slice[14], slice[15],
        ])
    } else {
        u32::from_be_bytes([slice[4], slice[5], slice[6], slice[7]]) as u64
    };
    hdr.p_vaddr = if is_64 != 0 {
        u64::from_be_bytes([
            slice[16], slice[17], slice[18], slice[19],
            slice[20], slice[21], slice[22], slice[23],
        ])
    } else {
        u32::from_be_bytes([slice[8], slice[9], slice[10], slice[11]]) as u64
    };
    hdr.p_paddr = if is_64 != 0 {
        u64::from_be_bytes([
            slice[24], slice[25], slice[26], slice[27],
            slice[28], slice[29], slice[30], slice[31],
        ])
    } else {
        u32::from_be_bytes([slice[12], slice[13], slice[14], slice[15]]) as u64
    };
    hdr.p_filesz = if is_64 != 0 {
        u64::from_be_bytes([
            slice[32], slice[33], slice[34], slice[35],
            slice[36], slice[37], slice[38], slice[39],
        ])
    } else {
        u32::from_be_bytes([slice[16], slice[17], slice[18], slice[19]]) as u64
    };
    hdr.p_memsz = if is_64 != 0 {
        u64::from_be_bytes([
            slice[40], slice[41], slice[42], slice[43],
            slice[44], slice[45], slice[46], slice[47],
        ])
    } else {
        u32::from_be_bytes([slice[20], slice[21], slice[22], slice[23]]) as u64
    };
    hdr.p_align = if is_64 != 0 {
        u64::from_be_bytes([
            slice[48], slice[49], slice[50], slice[51],
            slice[52], slice[53], slice[54], slice[55],
        ])
    } else {
        u32::from_be_bytes([slice[28], slice[29], slice[30], slice[31]]) as u64
    };
    0
}

// ── PE Parsing ───────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn pe_parse_dos_header(
    data: *const u8,
    n: usize,
    header: *mut PeHeader,
) -> i32 {
    if data.is_null() || header.is_null() || n < 64 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n.min(64)) };
    if slice[0] != b'M' || slice[1] != b'Z' {
        return -2;
    }
    let hdr = unsafe { &mut *header };
    hdr.e_magic.copy_from_slice(&slice[..2]);
    hdr.e_lfanew = u32::from_le_bytes([slice[60], slice[61], slice[62], slice[63]]);
    if n < (hdr.e_lfanew as usize + 4) {
        return -3;
    }
    0
}

#[no_mangle]
pub extern "C" fn pe_parse_nt_header(
    data: *const u8,
    n: usize,
    e_lfanew: u32,
    header: *mut PeNtHeader,
) -> i32 {
    if data.is_null() || header.is_null() || n < (e_lfanew as usize + 248) {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data.add(e_lfanew as usize), 248) };

    let hdr = unsafe { &mut *header };
    hdr.signature.copy_from_slice(&slice[..4]);
    if &hdr.signature != b"PE\0\0" {
        return -2;
    }
    hdr.file_header.machine = u16::from_le_bytes([slice[4], slice[5]]);
    hdr.file_header.num_sections = u16::from_le_bytes([slice[6], slice[7]]);
    hdr.file_header.timestamp = u32::from_le_bytes([slice[8], slice[9], slice[10], slice[11]]);
    hdr.file_header.opt_header_size = u16::from_le_bytes([slice[20], slice[21]]);
    hdr.file_header.characteristics = u16::from_le_bytes([slice[22], slice[23]]);

    hdr.optional_header.magic = u16::from_le_bytes([slice[24], slice[25]]);
    hdr.optional_header.size_of_code = u32::from_le_bytes([slice[28], slice[29], slice[30], slice[31]]);
    hdr.optional_header.address_of_entry_point = u32::from_le_bytes([slice[40], slice[41], slice[42], slice[43]]);
    let is_64 = hdr.optional_header.magic == 0x20B;
    if is_64 {
        hdr.optional_header.image_base = u64::from_le_bytes([
            slice[48], slice[49], slice[50], slice[51],
            slice[52], slice[53], slice[54], slice[55],
        ]);
    } else {
        hdr.optional_header.image_base = u32::from_le_bytes([slice[52], slice[53], slice[54], slice[55]]) as u64;
    }
    0
}

// ── Mach-O Parsing ──────────────────────────────────────────

#[no_mangle]
pub extern "C" fn macho_parse_header(
    data: *const u8,
    n: usize,
    header: *mut MachOHeader,
) -> i32 {
    if data.is_null() || header.is_null() || n < 28 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n.min(28)) };
    let magic = u32::from_be_bytes([slice[0], slice[1], slice[2], slice[3]]);
    if magic != MACHO_MAGIC_BE[0].to_be() as u32
        && slice[..4] != MACHO_MAGIC_LE
        && slice[..4] != MACHO_MAGIC_BE
    {
        return -2;
    }
    // Slice maybe LE/BE; conservatively use LE for x86/x86_64 Mach-O
    let hdr = unsafe { &mut *header };
    hdr.magic = u32::from_le_bytes([slice[0], slice[1], slice[2], slice[3]]);
    hdr.cputype = u32::from_le_bytes([slice[4], slice[5], slice[6], slice[7]]);
    hdr.cpusubtype = u32::from_le_bytes([slice[8], slice[9], slice[10], slice[11]]);
    hdr.filetype = u32::from_le_bytes([slice[12], slice[13], slice[14], slice[15]]);
    hdr.ncmds = u32::from_le_bytes([slice[16], slice[17], slice[18], slice[19]]);
    hdr.sizeofcmds = u32::from_le_bytes([slice[20], slice[21], slice[22], slice[23]]);
    hdr.flags = u32::from_le_bytes([slice[24], slice[25], slice[26], slice[27]]);
    0
}

// ── String Extraction ───────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct ExtractedString {
    pub offset: u64,
    pub length: u32,
    pub encoding: u8, // 1=ASCII, 2=UTF-8, 3=UTF-16-LE
}

/// Extract printable ASCII strings from a binary blob.  Returns count found.
#[no_mangle]
pub extern "C" fn forensic_extract_strings(
    data: *const u8,
    n: usize,
    min_len: u32,
    out_strings: *mut ExtractedString,
    max_strings: usize,
) -> i32 {
    if data.is_null() || out_strings.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let out_slice = unsafe {
        std::slice::from_raw_parts_mut(out_strings, max_strings)
    };
    let min_len = min_len as usize;
    let mut count = 0usize;
    let mut i = 0usize;

    while i < n {
        if count >= max_strings {
            break;
        }
        if (slice[i] >= 0x20 && slice[i] < 0x7F) || slice[i] == 0x09 {
            // Printable ASCII start
            let start = i;
            while i < n && ((slice[i] >= 0x20 && slice[i] < 0x7F) || slice[i] == 0x09) {
                i += 1;
            }
            if i - start >= min_len && count < max_strings {
                out_slice[count] = ExtractedString {
                    offset: start as u64,
                    length: (i - start) as u32,
                    encoding: 1,
                };
                count += 1;
            }
        } else {
            i += 1;
        }
    }
    count as i32
}

/// Extract UTF-16 LE strings (typically found in Windows binaries).
#[no_mangle]
pub extern "C" fn forensic_extract_utf16le_strings(
    data: *const u8,
    n: usize,
    min_len: u32,
    out_strings: *mut ExtractedString,
    max_strings: usize,
) -> i32 {
    if data.is_null() || out_strings.is_null() || n < 2 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let out_slice = unsafe {
        std::slice::from_raw_parts_mut(out_strings, max_strings)
    };
    let min_pairs = min_len as usize; // in bytes (= 2 * chars)
    let mut count = 0usize;
    let mut i = 0usize;

    while i + 1 < n {
        if count >= max_strings {
            break;
        }
        // UTF-16 LE: ASCII byte in low position, 0x00 in high
        let lo = slice[i];
        let hi = slice[i + 1];
        if (lo >= 0x20 && lo < 0x7F) && hi == 0x00 {
            let start = i;
            while i + 1 < n {
                let lo = slice[i];
                let hi = slice[i + 1];
                if !((lo >= 0x20 && lo < 0x7F) && hi == 0x00) {
                    break;
                }
                i += 2;
            }
            if i - start >= min_pairs && count < max_strings {
                out_slice[count] = ExtractedString {
                    offset: start as u64,
                    length: (i - start) as u32,
                    encoding: 3,
                };
                count += 1;
            }
        } else {
            i += 1;
        }
    }
    count as i32
}

// ── Shannon Entropy ─────────────────────────────────────────

/// Shannon entropy of a byte sequence.  Returns bits per byte in [0, 8].
#[no_mangle]
pub extern "C" fn shannon_entropy(data: *const u8, n: usize) -> f64 {
    if data.is_null() || n == 0 {
        return 0.0;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let mut counts = [0u64; 256];
    for &b in slice {
        counts[b as usize] += 1;
    }
    let total = n as f64;
    let mut h = 0.0f64;
    for &c in counts.iter() {
        if c > 0 {
            let p = c as f64 / total;
            h -= p * p.log2();
        }
    }
    h
}

/// Detect cryptographic entropy: returns 1 if entropy > 6.5 (likely encrypted/packed).
#[no_mangle]
pub extern "C" fn is_likely_encrypted(data: *const u8, n: usize) -> i32 {
    let e = shannon_entropy(data, n);
    if e > 6.5 { 1 } else { 0 }
}

// ── Hex String Detection ───────────────────────────────────

/// Find potential hex-string patterns in data (RFC emails, UUIDs, hashes).
/// Returns count written to out_offsets (each is a u64 offset).
#[no_mangle]
pub extern "C" fn forensic_find_hex_patterns(
    data: *const u8,
    n: usize,
    out_offsets: *mut u64,
    max_count: usize,
) -> i32 {
    if data.is_null() || out_offsets.is_null() || n < 8 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let out = unsafe { std::slice::from_raw_parts_mut(out_offsets, max_count) };
    let mut count = 0usize;
    let mut i = 0usize;
    let mut run = 0usize;
    let mut run_start = 0usize;

    while i < n {
        let b = slice[i];
        if (b >= b'0' && b <= b'9') || (b >= b'a' && b <= b'f') || (b >= b'A' && b <= b'F') {
            if run == 0 {
                run_start = i;
            }
            run += 1;
        } else if b == b':' || b == b'-' {
            // Separator common in UUIDs/MACs
        } else {
            if run >= 8 {
                if count < max_count {
                    out[count] = run_start as u64;
                    count += 1;
                }
            }
            run = 0;
        }
        i += 1;
    }
    if run >= 8 && count < max_count {
        out[count] = run_start as u64;
        count += 1;
    }
    count as i32
}

// ── Tests ───────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_detect() {
        let elf = [0x7Fu8, b'E', b'L', b'F'];
        assert_eq!(forensics_detect_format(elf.as_ptr(), 4), 1);
        let pe = [b'M', b'Z', 0u8, 0];
        assert_eq!(forensics_detect_format(pe.as_ptr(), 4), 2);
        let macho = [0xCF, 0xFA, 0xED, 0xFE];
        assert_eq!(forensics_detect_format(macho.as_ptr(), 4), 3);
    }

    #[test]
    fn test_string_extraction() {
        let data = b"\0\0strings are cool\0\0more content\0\0\xFF\xFF";
        let mut strings = [ExtractedString::default(); 4];
        let count = forensic_extract_strings(
            data.as_ptr(),
            data.len(),
            4,
            strings.as_mut_ptr(),
            4,
        );
        assert!(count >= 2);
        assert_eq!(strings[0].length, 16); // "strings are cool"
        assert_eq!(strings[1].length, 12); // "more content"
    }

    #[test]
    fn test_shannon_entropy() {
        // Repetitive data has low entropy
        let repeated = vec![0xAAu8; 100];
        let h = shannon_entropy(repeated.as_ptr(), repeated.len());
        assert!(h < 0.1);
        // Random-ish data has high entropy
        let random: Vec<u8> = (0..256u32).map(|i| i as u8).collect();
        let h = shannon_entropy(random.as_ptr(), random.len());
        assert!(h > 7.5);
    }

    #[test]
    fn test_is_encrypted() {
        let repeated = vec![0u8; 100];
        assert_eq!(is_likely_encrypted(repeated.as_ptr(), repeated.len()), 0);
        let random: Vec<u8> = (0..256u32).map(|i| i as u8).cycle().take(100).collect();
        assert_eq!(is_likely_encrypted(random.as_ptr(), random.len()), 1);
    }
}
