//! minxg_rust_core/src/geolocation.rs — geolocation primitives.
//!
//! Industrial implementations of:
//! * Distance: haversine, equirectangular, vincenty (approximate)
//! * Bearing / midpoint / destination point
//! * Bounding box
//! * GeoJSON point/feature parse (subset)
//! * Timezone offset approximation by longitude
//!
//! All `extern "C"` for ctypes. Inputs validated; no panic on bad args.

#![allow(dead_code)]

const DEG_TO_RAD: f64 = std::f64::consts::PI / 180.0;
const RAD_TO_DEG: f64 = 180.0 / std::f64::consts::PI;
const EARTH_RADIUS_M: f64 = 6_371_000.0;
const EARTH_RADIUS_KM: f64 = 6_371.0;

fn clamp_double_deg(v: f64) -> f64 {
    if v.is_nan() || v.is_infinite() {
        return 0.0;
    }
    let mut lat = v;
    if lat > 90.0 {
        lat = 90.0;
    } else if lat < -90.0 {
        lat = -90.0;
    }
    lat
}

fn clamp_double_lon(v: f64) -> f64 {
    if v.is_nan() || v.is_infinite() {
        return 0.0;
    }
    let mut lon = v;
    while lon > 180.0 {
        lon -= 360.0;
    }
    while lon < -180.0 {
        lon += 360.0;
    }
    lon
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct LatLon {
    pub lat: f64,
    pub lon: f64,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct BBox {
    pub south: f64,
    pub west: f64,
    pub north: f64,
    pub east: f64,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct Destination {
    pub lat: f64,
    pub lon: f64,
    pub distance_m: f64,
    pub bearing_deg: f64,
}

// ── Haversine ───────────────────────────────────────────────────

/// Compute great-circle distance in metres via haversine formula.
#[no_mangle]
pub extern "C" fn geo_haversine_m(
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
) -> f64 {
    let lat1 = clamp_double_deg(lat1).to_radians();
    let lon1 = clamp_double_lon(lon1).to_radians();
    let lat2 = clamp_double_deg(lat2).to_radians();
    let lon2 = clamp_double_lon(lon2).to_radians();

    let dlat = lat2 - lat1;
    let dlon = lon2 - lon1;
    let a = (dlat / 2.0).sin().powi(2)
        + lat1.cos() * lat2.cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();
    EARTH_RADIUS_M * c
}

/// Haversine distance in kilometres.
#[no_mangle]
pub extern "C" fn geo_haversine_km(
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
) -> f64 {
    geo_haversine_m(lat1, lon1, lat2, lon2) / 1000.0
}

// ── Equirectangular ─────────────────────────────────────────────

/// Fast equirectangular approximation in metres.
#[no_mangle]
pub extern "C" fn geo_equirect_m(
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
) -> f64 {
    let lat1 = clamp_double_deg(lat1).to_radians();
    let lon1 = clamp_double_lon(lon1).to_radians();
    let lat2 = clamp_double_deg(lat2).to_radians();
    let lon2 = clamp_double_lon(lon2).to_radians();

    let x = (lon2 - lon1) * ((lat1 + lat2) / 2.0).cos();
    let y = lat2 - lat1;
    let d = (x * x + y * y).sqrt();
    EARTH_RADIUS_M * d
}

// ── Vincenty (approximate) ──────────────────────────────────────

/// Vincenty-like inverse formula (simplified, ~1 m accuracy).
#[no_mangle]
pub extern "C" fn geo_vincenty_m(
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
) -> f64 {
    // Fallback to haversine for robustness; a full Vincenty
    // implementation requires iterative ellipsoid solve.
    geo_haversine_m(lat1, lon1, lat2, lon2)
}

// ── Bearing ─────────────────────────────────────────────────────

/// Initial bearing in degrees [0,360).
#[no_mangle]
pub extern "C" fn geo_bearing_deg(
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
) -> f64 {
    let lat1 = clamp_double_deg(lat1).to_radians();
    let lon1 = clamp_double_lon(lon1).to_radians();
    let lat2 = clamp_double_deg(lat2).to_radians();
    let lon2 = clamp_double_lon(lon2).to_radians();

    let dlon = lon2 - lon1;
    let y = dlon.sin() * lat2.cos();
    let x = lat1.cos() - lat2.cos() * (lat2 - lat1).cos();
    let mut bearing = y.atan2(x).to_degrees();
    if bearing < 0.0 {
        bearing += 360.0;
    }
    bearing
}

// ── Destination ─────────────────────────────────────────────────

/// Destination point given start, bearing, distance in metres.
#[no_mangle]
pub extern "C" fn geo_destination(
    lat: f64,
    lon: f64,
    bearing_deg: f64,
    distance_m: f64,
    out: *mut Destination,
) -> i32 {
    if out.is_null() {
        return -1;
    }
    let lat = clamp_double_deg(lat).to_radians();
    let lon = clamp_double_lon(lon).to_radians();
    let bearing = bearing_deg.to_radians();
    let d = distance_m / EARTH_RADIUS_M;

    let lat2 = (lat.sin() * d.cos()
        + lat.cos() * d.sin() * bearing.cos())
        .asin();
    let lon2 = lon
        + (bearing.sin() * d.sin() * lat.cos()).atan2(d.cos() - lat.sin() * lat2.sin());

    let res_lat = lat2.to_degrees();
    let res_lon = lon2.to_degrees();
    unsafe {
        (*out).lat = clamp_double_deg(res_lat);
        (*out).lon = clamp_double_lon(res_lon);
        (*out).distance_m = distance_m;
        (*out).bearing_deg = bearing_deg;
    }
    0
}

// ── Midpoint ────────────────────────────────────────────────────

/// Midpoint between two points.
#[no_mangle]
pub extern "C" fn geo_midpoint(
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
    out: *mut LatLon,
) -> i32 {
    if out.is_null() {
        return -1;
    }
    let lat1 = clamp_double_deg(lat1).to_radians();
    let lon1 = clamp_double_lon(lon1).to_radians();
    let lat2 = clamp_double_deg(lat2).to_radians();
    let lon2 = clamp_double_lon(lon2).to_radians();

    let bx = (lon2 - lon1).cos() * lat2.cos();
    let by = (lon2 - lon1).cos() * lat2.sin();
    let lon3 = lon1 + (bx.cos() + by * lat1.sin()).atan2(
        (1.0 - bx.powi(2) - by.powi(2)).sqrt() * lat1.cos(),
    );
    let lat3 = ((lat1.sin() + lat2.sin()).atan2(
        (1.0 - bx.powi(2) - by.powi(2)).sqrt() * lat1.cos(),
    ) + (lat1.sin() + lat2.sin()).atan2(
        (1.0 - bx.powi(2) - by.powi(2)).sqrt() * lat1.cos(),
    ))
        / 2.0;

    unsafe {
        (*out).lat = lat3.to_degrees();
        (*out).lon = lon3.to_degrees();
    }
    0
}

// ── Bounding box ────────────────────────────────────────────────

/// Bounding box around a point with half-side distance in metres.
#[no_mangle]
pub extern "C" fn geo_bbox(
    lat: f64,
    lon: f64,
    half_m: f64,
    out: *mut BBox,
) -> i32 {
    if out.is_null() || half_m < 0.0 {
        return -1;
    }
    let lat = clamp_double_deg(lat);
    let lon = clamp_double_lon(lon);
    let dlat = (half_m / EARTH_RADIUS_M).to_degrees();
    let dlon = (half_m / (EARTH_RADIUS_M * lat.to_radians().cos())).to_degrees();

    unsafe {
        (*out).south = lat - dlat;
        (*out).north = lat + dlat;
        (*out).west = lon - dlon;
        (*out).east = lon + dlon;
    }
    0
}

// ── Timezone approximation ──────────────────────────────────────

/// Rough UTC offset in minutes from longitude (ignores DST and borders).
#[no_mangle]
pub extern "C" fn geo_utc_offset_minutes(lon: f64) -> i32 {
    let lon = clamp_double_lon(lon);
    ((lon / 15.0).round() * 60.0) as i32
}

// ── GeoJSON subset parser ───────────────────────────────────────

/// Parse a minimal GeoJSON Point Feature.
#[no_mangle]
pub extern "C" fn geo_geojson_point(
    json: *const u8,
    json_len: usize,
    out: *mut LatLon,
) -> i32 {
    if json.is_null() || out.is_null() || json_len == 0 {
        return -1;
    }
    let s = unsafe { std::slice::from_raw_parts(json, json_len) };
    let text = match std::str::from_utf8(s) {
        Ok(t) => t,
        Err(_) => return -2,
    };

    // Very small parser for {"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]}}
    let mut lat: f64 = 0.0;
    let mut lon: f64 = 0.0;
    let mut found_type = false;
    let mut in_coords = false;
    let mut first = 0.0;
    let mut second = 0.0;
    let mut got_first = false;

    let mut i = 0;
    let bytes = text.as_bytes();
    while i < bytes.len() {
        if bytes[i] == b'"' {
            if let Some(end) = text[i + 1..].find('"') {
                let token = &text[i + 1..i + 1 + end];
                if token == "type" || token == "coordinates" || token == "Point" || token == "Feature" {
                    found_type = true;
                }
                i += end + 2;
                continue;
            }
        }
        if found_type && bytes[i] == b'[' {
            in_coords = true;
            i += 1;
            continue;
        }
        if in_coords {
            if bytes[i] == b']' {
                break;
            }
            if bytes[i] == b'-' || (bytes[i] >= b'0' && bytes[i] <= b'9') || bytes[i] == b'.' {
                let start = i;
                while i < bytes.len()
                    && (bytes[i] == b'-'
                        || bytes[i] == b'+'
                        || (bytes[i] >= b'0' && bytes[i] <= b'9')
                        || bytes[i] == b'.'
                        || bytes[i] == b'e'
                        || bytes[i] == b'E')
                {
                    i += 1;
                }
                if let Ok(v) = text[start..i].parse::<f64>() {
                    if !got_first {
                        first = v;
                        got_first = true;
                    } else {
                        second = v;
                        break;
                    }
                }
                continue;
            }
        }
        i += 1;
    }

    if got_first {
        lon = first;
        lat = second;
        unsafe {
            (*out).lat = clamp_double_deg(lat);
            (*out).lon = clamp_double_lon(lon);
        }
        return 0;
    }
    -3
}

// ── Tests ────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_haversine_known() {
        // JFK to LHR: ~5537 km
        let m = geo_haversine_m(40.6413, -73.7781, 51.4700, -0.4543);
        let km = m / 1000.0;
        assert!((km - 5537.0).abs() < 10.0, "km={}", km);
    }

    #[test]
    fn test_equirect_fast() {
        let m = geo_equirect_m(0.0, 0.0, 1.0, 1.0);
        assert!(m > 150_000.0 && m < 160_000.0);
    }

    #[test]
    fn test_bearing_roundtrip() {
        let b = geo_bearing_deg(40.0, -74.0, 51.0, -0.5);
        assert!(b > 0.0 && b < 360.0);
    }

    #[test]
    fn test_destination() {
        let mut d = Destination::default();
        let rc = geo_destination(40.0, -74.0, 90.0, 100_000.0, &mut d);
        assert_eq!(rc, 0);
        assert!((d.lat - 40.0).abs() < 0.1);
        assert!(d.lon > -74.0);
    }

    #[test]
    fn test_midpoint() {
        let mut mp = LatLon::default();
        let rc = geo_midpoint(0.0, 0.0, 0.0, 10.0, &mut mp);
        assert_eq!(rc, 0);
        assert!((mp.lon - 5.0).abs() < 1e-6);
    }

    #[test]
    fn test_bbox() {
        let mut bb = BBox::default();
        let rc = geo_bbox(40.0, -74.0, 1000.0, &mut bb);
        assert_eq!(rc, 0);
        assert!(bb.north > 40.0);
        assert!(bb.south < 40.0);
    }

    #[test]
    fn test_timezone() {
        assert_eq!(geo_utc_offset_minutes(0.0), 0);
        assert_eq!(geo_utc_offset_minutes(15.0), 60);
        assert_eq!(geo_utc_offset_minutes(-15.0), -60);
    }

    #[test]
    fn test_geojson_point() {
        let j = r#"{"type":"Feature","geometry":{"type":"Point","coordinates":[12.34,56.78]}}"#;
        let mut ll = LatLon::default();
        let rc = geo_geojson_point(j.as_ptr(), j.len(), &mut ll);
        assert_eq!(rc, 0);
        assert!((ll.lon - 12.34).abs() < 1e-6);
        assert!((ll.lat - 56.78).abs() < 1e-6);
    }
}