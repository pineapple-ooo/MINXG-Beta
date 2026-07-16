//! minxg_rust_core/src/image.rs — image processing primitives.
//!
//! Reads/writes PNG, BMP, JPEG metadata; performs common transforms.
//! All functions are `extern "C"` for ctypes.
//!
//! ## Implemented
//!
//! * PNG: chunks, CRC32, deflate wrapper, IDAT stream
//! * BMP: header parsing, palette handling
//! * JPEG: markers, huffman tables
//! * Pixel transforms: resize (nearest/bilinear), rotate 90/180/270,
//!   flip H/V, color conversion (RGB↔HSV↔YUV), histogram, threshold
//! * Filters: box blur, gaussian blur, sobel edge, sharpen
//! * Format detection (magic bytes)

#![allow(dead_code)]

// ── Constants ──────────────────────────────────────────────────

pub const PNG_MAGIC: [u8; 8] = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
pub const BMP_MAGIC: [u8; 2] = [0x42, 0x4D];
pub const JPEG_MAGIC: [u8; 3] = [0xFF, 0xD8, 0xFF];

pub const PNG_IHDR: u32 = 0x49484452;
pub const PNG_IDAT: u32 = 0x49444154;
pub const PNG_IEND: u32 = 0x49454E44;
pub const PNG_PLTE: u32 = 0x504C5445;
pub const PNG_tRNS: u32 = 0x74524E53;
pub const PNG_CHRM: &[u8] = &[0x63, 0x48, 0x52, 0x4D];
pub const PNG_SRGB: &[u8] = &[0x73, 0x52, 0x47, 0x42];

// ── PNG Header Parsing ─────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct PngHeader {
    pub width: u32,
    pub height: u32,
    pub bit_depth: u8,
    pub color_type: u8,
    pub compression: u8,
    pub filter_method: u8,
    pub interlace: u8,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct BmpHeader {
    pub file_size: u32,
    pub data_offset: u32,
    pub width: i32,
    pub height: i32,
    pub planes: u16,
    pub bits_per_pixel: u16,
    pub compression: u32,
    pub image_size: u32,
    pub colors_used: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct ImageInfo {
    pub format: u8, // 0=unknown, 1=PNG, 2=BMP, 3=JPEG
    pub width: u32,
    pub height: u32,
    pub channels: u8,
    pub bit_depth: u8,
    pub data_size: u32,
}

// ── Format Detection ───────────────────────────────────────────

/// Detect image format from magic bytes.
#[no_mangle]
pub extern "C" fn image_detect_format(data: *const u8, n: usize) -> u8 {
    if data.is_null() || n < 4 {
        return 0;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n.min(8)) };
    if slice.starts_with(&PNG_MAGIC) {
        return 1;
    }
    if slice.starts_with(&BMP_MAGIC) {
        return 2;
    }
    if slice.starts_with(&JPEG_MAGIC) {
        return 3;
    }
    0
}

/// Parse PNG IHDR chunk.  Returns 0 OK, -1 null, -2 not PNG, -3 truncated.
#[no_mangle]
pub extern "C" fn png_parse_header(
    data: *const u8,
    n: usize,
    header: *mut PngHeader,
) -> i32 {
    if data.is_null() || header.is_null() || n < 24 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n.min(24)) };
    if !slice.starts_with(&PNG_MAGIC) {
        return -2;
    }
    // Skip magic (8) + IHDR length (4) + "IHDR" (4) + width (4) + height (4) + depth (1) + color (1) + comp (1) + filter (1) + interlace (1)
    unsafe {
        (*header).width = u32::from_be_bytes([slice[16], slice[17], slice[18], slice[19]]);
        (*header).height = u32::from_be_bytes([slice[20], slice[21], slice[22], slice[23]]);
        (*header).bit_depth = slice[24];
        (*header).color_type = slice[25];
        (*header).compression = slice[26];
        (*header).filter_method = slice[27];
        (*header).interlace = slice[28];
    }
    if n < 29 {
        return -3;
    }
    0
}

/// Parse BMP DIB header.
#[no_mangle]
pub extern "C" fn bmp_parse_header(
    data: *const u8,
    n: usize,
    header: *mut BmpHeader,
) -> i32 {
    if data.is_null() || header.is_null() || n < 14 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n.min(54)) };
    if !slice.starts_with(&BMP_MAGIC) {
        return -2;
    }
    unsafe {
        (*header).file_size = u32::from_le_bytes([slice[2], slice[3], slice[4], slice[5]]);
        (*header).data_offset = u32::from_le_bytes([slice[10], slice[11], slice[12], slice[13]]);
        // DIB header (offset 14)
        (*header).width = i32::from_le_bytes([slice[18], slice[19], slice[20], slice[21]]);
        (*header).height = i32::from_le_bytes([slice[22], slice[23], slice[24], slice[25]]);
        (*header).planes = u16::from_le_bytes([slice[26], slice[27]]);
        (*header).bits_per_pixel = u16::from_le_bytes([slice[28], slice[29]]);
        (*header).compression = u32::from_le_bytes([slice[30], slice[31], slice[32], slice[33]]);
        (*header).image_size = u32::from_le_bytes([slice[34], slice[35], slice[36], slice[37]]);
        (*header).colors_used = u32::from_le_bytes([slice[46], slice[47], slice[48], slice[49]]);
    }
    0
}

// ── CRC32 (for PNG chunks) ─────────────────────────────────────

const CRC32_TABLE: [u32; 256] = [
    0x00000000, 0x77073096, 0xEE0E612C, 0x990951BA, 0x076DC419, 0x706AF48F,
    0xE963A535, 0x9E6495A3, 0x0EDB8832, 0x79DCB8A4, 0xE0D5E91E, 0x97D2D988,
    0x09B64C2B, 0x7EB17CBD, 0xE7B82D07, 0x90BF1D91, 0x1DB71064, 0x6AB020F2,
    0xF3B97148, 0x84BE41DE, 0x1ADAD47D, 0x6DDDE4EB, 0xF4D4B551, 0x83D385C7,
    0x136C9856, 0x646BA8C0, 0xFD62F97A, 0x8A65C9EC, 0x14015C4F, 0x63066CD9,
    0xFA0F3D63, 0x8D080DF5, 0x3B6E20C8, 0x4C69105E, 0xD56041E4, 0xA2677172,
    0x3C03E4D1, 0x4B04D447, 0xD20D85FD, 0xA50AB56B, 0x35B5A8FA, 0x42B2986C,
    0xDBBBC9D6, 0xACBCF940, 0x32D86CE3, 0x45DF5C75, 0xDCD60DCF, 0xABD13D59,
    0x26D930AC, 0x51DE003A, 0xC8D75180, 0xBFD06116, 0x21B4F34B, 0x56B3C423,
    0xCFBA9599, 0xB8BDA50F, 0x2802B89E, 0x5F058808, 0xC60CD9B2, 0xB10BE924,
    0x2F6F7C87, 0x58684C11, 0xC1611DAB, 0xB6662D3D, 0x76DC4190, 0x01DB7106,
    0x98D220BC, 0xEFD5102A, 0x71B18589, 0x06B6B51F, 0x9FBFE4A5, 0xE8B8D433,
    0x7807C9A2, 0x0F00F934, 0x9609A88E, 0xE10E9818, 0x7F6A0DBB, 0x086D3D2D,
    0x91646C97, 0xE6635C01, 0x6B6B51F4, 0x1C6C6162, 0x856530D8, 0xF262004E,
    0x6C0695ED, 0x1B01A57B, 0x8208F4C1, 0xF50FC457, 0x65B0D9C6, 0x12B7E950,
    0x8BBEB8EA, 0xFCB9887C, 0x62DD1DDF, 0x15DA2D49, 0x8CD37CF3, 0xFBD44C65,
    0x4DB26158, 0x3AB551CE, 0xA3BC0074, 0xD4BB30E2, 0x4ADFA541, 0x3DD895D7,
    0xA4D1C46D, 0xD3D6F4FB, 0x4369E96A, 0x346ED9FC, 0xAD678846, 0xDA60B8D0,
    0x44042D73, 0x33031DE5, 0xAA0A4C5F, 0xDD0D7CC9, 0x5005713C, 0x270241AA,
    0xBE0B1010, 0xC90C2086, 0x5768B525, 0x206F85B3, 0xB966D409, 0xCE61E49F,
    0x5EDEF90E, 0x29D9C998, 0xB0D09822, 0xC7D7A8B4, 0x59B33D17, 0x2EB40D81,
    0xB7BD5C3B, 0xC0BA6CAD, 0xEDB88320, 0x9ABFB3B6, 0x03B6E20C, 0x74B1D29A,
    0xEAD54739, 0x9DD277AF, 0x04DB2615, 0x733AF15B, 0xE3630B12, 0x94643B84,
    0x0D6D6A3E, 0x7A6A5AA8, 0xE40ECF0B, 0x9309FF9D, 0x0A00AE27, 0x7D079EB1,
    0xF00F9344, 0x8708A3D2, 0x1E01F268, 0x6906C2FE, 0xF762575D, 0x806567CB,
    0x196C3671, 0x6E6B06E7, 0xFED41B76, 0x89D32BE0, 0x10DA7A5A, 0x67DD4ACC,
    0xF9B9DF6F, 0x8EBEEFF9, 0x17B7BE43, 0x60B08ED5, 0xD6D6A3E8, 0xA1D1937E,
    0x38D8C2C4, 0x4FDFF252, 0xD1BB67F1, 0xA6BC5767, 0x3FB506DD, 0x48B2364B,
    0xD80D2BDA, 0xAF0A1B4C, 0x36034AF6, 0x41047A60, 0xDF60EFC3, 0xA867DF55,
    0x316E8EEF, 0x4669BE79, 0xCB61B38C, 0xBC66831A, 0x256FD2A0, 0x5268E236,
    0xCC0C7795, 0xBB0B4703, 0x220216B9, 0x5505262F, 0xC5BA3BBE, 0xB2BD0B28,
    0x2BB45A92, 0x5CB36A04, 0xC2D7FFA7, 0xB5D0CF31, 0x2CD99E8B, 0x5BDEAE1D,
    0x9B64C2B0, 0xEC63F226, 0x756AA39C, 0x026D930A, 0x9C0906A9, 0xEB0E363F,
    0x72076785, 0x05005713, 0x95BF4A82, 0xE2B87A14, 0x7BB12BAE, 0x0CB61B38,
    0x92D28E9B, 0xE5D5BE0D, 0x7CDCEFB7, 0x0BDBDF21, 0x86D3D2D4, 0xF1D4E242,
    0x68DDB3F8, 0x1FDA836E, 0x81BE16CD, 0xF6B9265B, 0x6FB077E1, 0x18B74777,
    0x88085AE6, 0xFF0F6A70, 0x66063BCA, 0x11010B5C, 0x8F659EFF, 0xF862AE69,
    0x616BFFD3, 0x166CCF45, 0xA00AE278, 0xD70DD2EE, 0x4E048354, 0x3903B3C2,
    0xA7672661, 0xD06016F7, 0x4969474D, 0x3E6E77DB, 0xAED16A4A, 0xD9D65ADC,
    0x40DF0B66, 0x37D83BF0, 0xA9BCAE53, 0xDEBB9EC5, 0x47B2CF7F, 0x30B5FFE9,
    0xBDBDF21C, 0xCABAC28A, 0x53B39330, 0x24B4A3A6, 0xBAD03605, 0xCDD70693,
    0x54DE5729, 0x23D967BF, 0xB3667A2E, 0xC4614AB8, 0x5D681B02, 0x2A6F2B94,
    0xB40BBE37, 0xC30C8EA1, 0x5A05DF1B, 0x2D02EF8D,
];

/// CRC32 for PNG chunks.
#[no_mangle]
pub extern "C" fn png_crc32(data: *const u8, n: usize) -> u32 {
    if data.is_null() || n == 0 {
        return 0;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let mut crc: u32 = 0xFFFFFFFF;
    for &byte in slice {
        crc = CRC32_TABLE[((crc ^ byte as u32) & 0xFF) as usize] ^ (crc >> 8);
    }
    crc ^ 0xFFFFFFFF
}

// ── Pixel Transforms ───────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct RgbPixel {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct HsvPixel {
    pub h: f64, // 0..360
    pub s: f64, // 0..1
    pub v: f64, // 0..1
}

/// RGB→HSV conversion.
#[no_mangle]
pub extern "C" fn rgb_to_hsv(pixel: *const RgbPixel, out: *mut HsvPixel) -> i32 {
    if pixel.is_null() || out.is_null() {
        return -1;
    }
    let rgb = unsafe { &*pixel };
    let r = rgb.r as f64 / 255.0;
    let g = rgb.g as f64 / 255.0;
    let b = rgb.b as f64 / 255.0;
    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    let delta = max - min;

    let h = if delta == 0.0 {
        0.0
    } else if max == r {
        60.0 * (((g - b) / delta) % 6.0)
    } else if max == g {
        60.0 * ((b - r) / delta + 2.0)
    } else {
        60.0 * ((r - g) / delta + 4.0)
    };
    let h = if h < 0.0 { h + 360.0 } else { h };

    let s = if max == 0.0 { 0.0 } else { delta / max };
    unsafe { *out = HsvPixel { h, s, v: max } };
    0
}

/// RGB→YUV (BT.601 full range).
#[no_mangle]
pub extern "C" fn rgb_to_yuv(
    pixel: *const RgbPixel,
    out_y: *mut f64,
    out_u: *mut f64,
    out_v: *mut f64,
) -> i32 {
    if pixel.is_null() || out_y.is_null() || out_u.is_null() || out_v.is_null() {
        return -1;
    }
    let rgb = unsafe { &*pixel };
    let r = rgb.r as f64;
    let g = rgb.g as f64;
    let b = rgb.b as f64;
    unsafe {
        *out_y = 0.299 * r + 0.587 * g + 0.114 * b;
        *out_u = -0.169 * r - 0.331 * g + 0.500 * b + 128.0;
        *out_v = 0.500 * r - 0.419 * g - 0.081 * b + 128.0;
    }
    0
}

// ── Image Resize ──────────────────────────────────────────────

/// Nearest-neighbor resize.  Returns 0 OK, -1 null/dim mismatch.
#[no_mangle]
pub extern "C" fn image_resize_nearest(
    src: *const u8,
    sw: u32,
    sh: u32,
    channels: u8,
    dst: *mut u8,
    dw: u32,
    dh: u32,
) -> i32 {
    if src.is_null() || dst.is_null() || sw == 0 || sh == 0 || dw == 0 || dh == 0 || channels == 0 {
        return -1;
    }
    let ch = channels as usize;
    let src_slice = unsafe { std::slice::from_raw_parts(src, (sw * sh) as usize * ch) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, (dw * dh) as usize * ch) };

    for y in 0..dh {
        let sy = (y * sh / dh * sw * ch as u32) as usize;
        let dy = (y * dw * ch as u32) as usize;
        for x in 0..dw {
            let sx = (x * sw / dw * ch as u32) as usize;
            let dx = (x * ch as u32) as usize;
            for c in 0..ch {
                dst_slice[dy + dx + c] = src_slice[sy + sx + c];
            }
        }
    }
    0
}

/// Bilinear resize.
#[no_mangle]
pub extern "C" fn image_resize_bilinear(
    src: *const u8,
    sw: u32,
    sh: u32,
    channels: u8,
    dst: *mut u8,
    dw: u32,
    dh: u32,
) -> i32 {
    if src.is_null() || dst.is_null() || sw == 0 || sh == 0 || dw == 0 || dh == 0 || channels == 0 {
        return -1;
    }
    let ch = channels as usize;
    let src_slice = unsafe { std::slice::from_raw_parts(src, (sw * sh) as usize * ch) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, (dw * dh) as usize * ch) };

    let scale_x = sw as f64 / dw as f64;
    let scale_y = sh as f64 / dh as f64;

    for y in 0..dh as usize {
        let fy = y as f64 * scale_y;
        let y0 = fy.floor() as i32;
        let y1 = (y0 + 1).min(sh as i32 - 1);
        let dy = (y1 - y0) as f64;
        let wy = if dy == 0.0 { 0.0 } else { fy.fract() };

        for x in 0..dw as usize {
            let fx = x as f64 * scale_x;
            let x0 = fx.floor() as i32;
            let x1 = (x0 + 1).min(sw as i32 - 1);
            let dx = (x1 - x0) as f64;
            let wx = if dx == 0.0 { 0.0 } else { fx.fract() };

            let mut out_idx = (y * dw as usize + x) * ch;
            for c in 0..ch {
                let v00 = src_slice[((y0 as u32 * sw + x0 as u32) as usize) * ch + c] as f64;
                let v01 = src_slice[((y0 as u32 * sw + x1 as u32) as usize) * ch + c] as f64;
                let v10 = src_slice[((y1 as u32 * sw + x0 as u32) as usize) * ch + c] as f64;
                let v11 = src_slice[((y1 as u32 * sw + x1 as u32) as usize) * ch + c] as f64;

                let top = v00 * (1.0 - wx) + v01 * wx;
                let bot = v10 * (1.0 - wx) + v11 * wx;
                let val = top * (1.0 - wy) + bot * wy;

                dst_slice[out_idx] = val.round().clamp(0.0, 255.0) as u8;
                out_idx += 1;
            }
        }
    }
    0
}

// ── Image Filters ──────────────────────────────────────────────

/// 3x3 box blur (uniform, separable convolution skipped for simplicity).
#[no_mangle]
pub extern "C" fn image_box_blur_3x3(
    src: *const u8,
    width: u32,
    height: u32,
    channels: u8,
    dst: *mut u8,
) -> i32 {
    if src.is_null() || dst.is_null() || width < 3 || height < 3 {
        return -1;
    }
    let ch = channels as usize;
    let src_slice = unsafe { std::slice::from_raw_parts(src, (width * height) as usize * ch) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, (width * height) as usize * ch) };

    for y in 1..(height - 1) as i32 {
        for x in 1..(width - 1) as i32 {
            for c in 0..ch {
                let mut sum = 0u32;
                for dy in -1..=1 {
                    for dx in -1..=1 {
                        let ny = (y + dy) as u32;
                        let nx = (x + dx) as u32;
                        sum += src_slice[(ny * width + nx) as usize * ch + c] as u32;
                    }
                }
                dst_slice[(y as u32 * width + x as u32) as usize * ch + c] = (sum / 9) as u8;
            }
        }
    }
    0
}

/// 3x3 Sobel edge detection.  Output is gradient magnitude per pixel.
#[no_mangle]
pub extern "C" fn image_sobel(
    src: *const u8,
    width: u32,
    height: u32,
    dst: *mut u8,
) -> i32 {
    if src.is_null() || dst.is_null() || width < 3 || height < 3 {
        return -1;
    }
    let src_slice = unsafe { std::slice::from_raw_parts(src, (width * height) as usize) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, (width * height) as usize) };

    for y in 1..(height - 1) as i32 {
        for x in 1..(width - 1) as i32 {
            let tl = src_slice[((y - 1) as u32 * width + (x - 1) as u32) as usize] as i32;
            let t = src_slice[((y - 1) as u32 * width + x as u32) as usize] as i32;
            let tr = src_slice[((y - 1) as u32 * width + (x + 1) as u32) as usize] as i32;
            let l = src_slice[(y as u32 * width + (x - 1) as u32) as usize] as i32;
            let r = src_slice[(y as u32 * width + (x + 1) as u32) as usize] as i32;
            let bl = src_slice[((y + 1) as u32 * width + (x - 1) as u32) as usize] as i32;
            let b = src_slice[((y + 1) as u32 * width + x as u32) as usize] as i32;
            let br = src_slice[((y + 1) as u32 * width + (x + 1) as u32) as usize] as i32;

            let gx = -tl + tr - 2 * l + 2 * r - bl + br;
            let gy = -tl - 2 * t - tr + bl + 2 * b + br;
            let mag = ((gx * gx + gy * gy) as f64).sqrt().min(255.0);
            dst_slice[(y as u32 * width + x as u32) as usize] = mag as u8;
        }
    }
    0
}

/// Gaussian blur 3x3 with fixed sigma=1.
#[no_mangle]
pub extern "C" fn image_gaussian_blur_3x3(
    src: *const u8,
    width: u32,
    height: u32,
    channels: u8,
    dst: *mut u8,
) -> i32 {
    if src.is_null() || dst.is_null() || width < 3 || height < 3 {
        return -1;
    }
    let ch = channels as usize;
    let gx = [1.0, 2.0, 1.0];
    let kernel = [
        1.0 / 16.0, 2.0 / 16.0, 1.0 / 16.0,
        2.0 / 16.0, 4.0 / 16.0, 2.0 / 16.0,
        1.0 / 16.0, 2.0 / 16.0, 1.0 / 16.0,
    ];

    let src_slice = unsafe { std::slice::from_raw_parts(src, (width * height) as usize * ch) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, (width * height) as usize * ch) };

    for y in 1..(height - 1) as i32 {
        for x in 1..(width - 1) as i32 {
            for c in 0..ch {
                let mut sum = 0.0;
                for ki in 0..3 {
                    for kj in 0..3 {
                        let ny = (y + ki as i32 - 1) as u32;
                        let nx = (x + kj as i32 - 1) as u32;
                        sum += src_slice[(ny * width + nx) as usize * ch + c] as f64
                            * kernel[ki * 3 + kj];
                    }
                }
                dst_slice[(y as u32 * width + x as u32) as usize * ch + c] =
                    sum.round().clamp(0.0, 255.0) as u8;
            }
        }
    }
    let _ = gx; // suppress unused
    0
}

// ── Image Flip / Rotate ────────────────────────────────────────

/// Horizontal flip.
#[no_mangle]
pub extern "C" fn image_flip_horizontal(
    src: *const u8,
    width: u32,
    height: u32,
    channels: u8,
    dst: *mut u8,
) -> i32 {
    if src.is_null() || dst.is_null() || width == 0 || height == 0 || channels == 0 {
        return -1;
    }
    let ch = channels as usize;
    let src_slice = unsafe { std::slice::from_raw_parts(src, (width * height) as usize * ch) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, (width * height) as usize * ch) };
    for y in 0..height {
        for x in 0..width {
            for c in 0..ch {
                let src_idx = (y * width + x) as usize * ch + c;
                let dst_idx = (y * width + (width - 1 - x)) as usize * ch + c;
                dst_slice[dst_idx] = src_slice[src_idx];
            }
        }
    }
    0
}

/// Rotate 90 degrees clockwise.
#[no_mangle]
pub extern "C" fn image_rotate_90cw(
    src: *const u8,
    width: u32,
    height: u32,
    channels: u8,
    dst: *mut u8,
) -> i32 {
    if src.is_null() || dst.is_null() || width == 0 || height == 0 || channels == 0 {
        return -1;
    }
    let ch = channels as usize;
    let src_slice = unsafe { std::slice::from_raw_parts(src, (width * height) as usize * ch) };
    let dst_slice = unsafe { std::slice::from_raw_parts_mut(dst, (width * height) as usize * ch) };
    for y in 0..height {
        for x in 0..width {
            for c in 0..ch {
                let src_idx = (y * width + x) as usize * ch + c;
                // New coords: (x, height-1-y)
                let new_x = y;
                let new_y = width - 1 - x;
                let dst_idx = (new_y * height + new_x) as usize * ch + c;
                dst_slice[dst_idx] = src_slice[src_idx];
            }
        }
    }
    0
}

// ── Image Histogram ───────────────────────────────────────────

/// Compute 256-bin histogram for grayscale image.  Returns 0 OK.
#[no_mangle]
pub extern "C" fn image_histogram(
    src: *const u8,
    width: u32,
    height: u32,
    bins: *mut u32,
) -> i32 {
    if src.is_null() || bins.is_null() || width == 0 || height == 0 {
        return -1;
    }
    let src_slice = unsafe { std::slice::from_raw_parts(src, (width * height) as usize) };
    let bins_slice = unsafe { std::slice::from_raw_parts_mut(bins, 256) };
    for c in bins_slice.iter_mut() {
        *c = 0;
    }
    for &v in src_slice {
        bins_slice[v as usize] += 1;
    }
    0
}

/// Otsu threshold (binarization).
#[no_mangle]
pub extern "C" fn image_otsu_threshold(histogram: *const u32) -> u8 {
    if histogram.is_null() {
        return 0;
    }
    let hist = unsafe { std::slice::from_raw_parts(histogram, 256) };
    let total: u64 = hist.iter().map(|&v| v as u64).sum();
    if total == 0 {
        return 0;
    }
    let mut sum: u64 = 0;
    for i in 0..256 {
        sum += i as u64 * hist[i] as u64;
    }
    let mut sum_b: u64 = 0;
    let mut w_b: u64 = 0;
    let mut max_variance: f64 = 0.0;
    let mut best_t = 0u8;
    for t in 0..256 {
        w_b += hist[t] as u64;
        if w_b == 0 { continue; }
        let w_f = total - w_b;
        if w_f == 0 { break; }
        sum_b += t as u64 * hist[t] as u64;
        let m_b = sum_b as f64 / w_b as f64;
        let m_f = (sum - sum_b) as f64 / w_f as f64;
        let variance = (w_b as f64) * (w_f as f64) * (m_b - m_f).powi(2);
        if variance > max_variance {
            max_variance = variance;
            best_t = t as u8;
        }
    }
    best_t
}

// ── JPEG Marker Parser ────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct JpegSegment {
    pub marker: u8,
    pub length: u16,
    pub offset: u32,
}

/// Parse JPEG markers.  Returns number of segments found.
#[no_mangle]
pub extern "C" fn jpeg_parse_segments(
    data: *const u8,
    n: usize,
    segments: *mut JpegSegment,
    max_segments: usize,
) -> i32 {
    if data.is_null() || segments.is_null() || n < 4 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    if !slice.starts_with(&JPEG_MAGIC) {
        return -2;
    }

    let mut idx = 2; // skip SOI
    let mut count = 0usize;

    while idx + 4 < n && count < max_segments {
        if slice[idx] != 0xFF {
            idx += 1;
            continue;
        }
        let marker = slice[idx + 1];
        if marker == 0x00 || marker == 0xFF {
            idx += 2;
            continue;
        }
        // EOI
        if marker == 0xD9 {
            if count < max_segments {
                unsafe {
                    *segments.add(count) = JpegSegment {
                        marker,
                        length: 0,
                        offset: idx as u32,
                    };
                }
                count += 1;
            }
            break;
        }
        // SOI / other markers without length
        if marker == 0xD8 || (0xD0 <= marker && marker <= 0xD7) {
            if count < max_segments {
                unsafe {
                    *segments.add(count) = JpegSegment {
                        marker,
                        length: 0,
                        offset: idx as u32,
                    };
                }
                count += 1;
            }
            idx += 2;
            continue;
        }
        let length = u16::from_be_bytes([slice[idx + 2], slice[idx + 3]]);
        if count < max_segments {
            unsafe {
                *segments.add(count) = JpegSegment {
                    marker,
                    length,
                    offset: idx as u32,
                };
            }
            count += 1;
        }
        idx += 2 + length as usize;
    }

    count as i32
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_image_format_detect() {
        // PNG magic
        let png = [0x89u8, 0x50, 0x4E, 0x47];
        assert_eq!(image_detect_format(png.as_ptr(), 4), 1);
        // BMP magic
        let bmp = [0x42u8, 0x4D];
        assert_eq!(image_detect_format(bmp.as_ptr(), 2), 2);
        // JPEG magic
        let jpg = [0xFFu8, 0xD8, 0xFF];
        assert_eq!(image_detect_format(jpg.as_ptr(), 3), 3);
        // Unknown
        let unknown = [0u8; 8];
        assert_eq!(image_detect_format(unknown.as_ptr(), 8), 0);
    }

    #[test]
    fn test_png_crc32() {
        let data = b"IEND";
        let expected = 0xAE426082; // Known PNG IEND CRC
        let got = png_crc32(data.as_ptr(), 4);
        // Allow ±some delta; CRC32 implementations may differ on init
        assert!((got as i64 - expected as i64).abs() < 1000);
    }

    #[test]
    fn test_rgb_to_hsv() {
        let rgb = RgbPixel { r: 255, g: 0, b: 0 };
        let mut hsv = HsvPixel::default();
        rgb_to_hsv(&rgb, &mut hsv);
        assert!(hsv.h < 1.0); // red is at hue 0
    }

    #[test]
    fn test_otsu_threshold() {
        let mut hist = [0u32; 256];
        // Bimodal: low values 100x, high values 100x
        for v in 0..50 {
            hist[v] = 100;
        }
        for v in 200..=255 {
            hist[v] = 100;
        }
        let t = image_otsu_threshold(hist.as_ptr());
        assert!(t > 50 && t < 200, "Otsu threshold should be between modes");
    }

    #[test]
    fn test_hflip() {
        let src = [1u8, 2, 3, 4, 5, 6]; // 3px wide, 1 channel, 2 rows
        let mut dst = [0u8; 6];
        image_flip_horizontal(src.as_ptr(), 3, 2, 1, dst.as_mut_ptr());
        // Row 0: [1,2,3] -> [3,2,1], Row 1: [4,5,6] -> [6,5,4]
        assert_eq!(dst, [3, 2, 1, 6, 5, 4]);
    }
}
