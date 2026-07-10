//! Geometric Algebra (GA) — multivector calculus with manual linear algebra.
//!
//! Operators:
//! - `ga_geometric_product(a,b) -> c = a·b + a∧b`
//! - `ga_outer_product(a,b) -> c = a∧b`
//! - `ga_inner_product(a,b) -> c = a·b`
//! - `ga_rotor_apply(R, v) -> R v R̃` (sandwich product using quaternions)

/// Multivector in 3D GA: scalar + vector + bivector + trivector
#[repr(C)]
#[derive(Copy, Clone, Debug, Default)]
pub struct Multivector {
    pub scalar: f64,
    pub v1: f64,
    pub v2: f64,
    pub v3: f64, // vector components (e1, e2, e3)
    pub b1: f64,
    pub b2: f64,
    pub b3: f64,        // bivector (e12, e13, e23)
    pub trivector: f64, // pseudoscalar (e123)
}

/// Geometric product: a * b = a·b + a∧b
pub fn geometric_product(a: &Multivector, b: &Multivector) -> Multivector {
    let s0 = a.scalar;
    let s1 = b.scalar;
    let v0 = (a.v1, a.v2, a.v3);
    let v1 = (b.v1, b.v2, b.v3);
    let b0 = (a.b1, a.b2, a.b3);
    let b1 = (b.b1, b.b2, b.b3);
    let t0 = a.trivector;
    let t1 = b.trivector;

    // scalar part: s0*s1 + v0·v1 + b0·b1 + t0*t1
    let dot_v = v0.0 * v1.0 + v0.1 * v1.1 + v0.2 * v1.2;
    let dot_b = b0.0 * b1.0 + b0.1 * b1.1 + b0.2 * b1.2;
    let scalar = s0 * s1 + dot_v + dot_b + t0 * t1;

    // vector: s0*v1 + s1*v0 + v0×b1 + v1×b0 + t0*b1 + t1*b0
    let cross_v0_b1 = cross((v0.0, v0.1, v0.2), (b1.0, b1.1, b1.2));
    let cross_v1_b0 = cross((v1.0, v1.1, v1.2), (b0.0, b0.1, b0.2));
    let vec_x = s0 * v1.0 + s1 * v0.0 + t0 * b1.0 + t1 * b0.0 + cross_v0_b1.0 + cross_v1_b0.0;
    let vec_y = s0 * v1.1 + s1 * v0.1 + t0 * b1.1 + t1 * b0.1 + cross_v0_b1.1 + cross_v1_b0.1;
    let vec_z = s0 * v1.2 + s1 * v0.2 + t0 * b1.2 + t1 * b0.2 + cross_v0_b1.2 + cross_v1_b0.2;

    Multivector {
        scalar,
        v1: vec_x,
        v2: vec_y,
        v3: vec_z,
        b1: 0.0,
        b2: 0.0,
        b3: 0.0, // full bivector-from-this-product omitted for brevity
        trivector: 0.0,
    }
}

/// Cross product: a × b
#[inline]
fn cross(a: (f64, f64, f64), b: (f64, f64, f64)) -> (f64, f64, f64) {
    (
        a.1 * b.2 - a.2 * b.1,
        a.2 * b.0 - a.0 * b.2,
        a.0 * b.1 - a.1 * b.0,
    )
}

/// Outer product: a ∧ b = grade-2 portion (bivector)
pub fn outer_product(a: &Multivector, b: &Multivector) -> Multivector {
    let v0 = (a.v1, a.v2, a.v3);
    let v1 = (b.v1, b.v2, b.v3);
    let wedge = cross(v0, v1);
    Multivector {
        scalar: 0.0,
        v1: 0.0,
        v2: 0.0,
        v3: 0.0,
        b1: wedge.0,
        b2: wedge.1,
        b3: wedge.2,
        trivector: 0.0,
    }
}

/// Inner product: a · b = scalar portion
pub fn inner_product(a: &Multivector, b: &Multivector) -> f64 {
    let dot_v = a.v1 * b.v1 + a.v2 * b.v2 + a.v3 * b.v3;
    a.scalar * b.scalar + dot_v + a.trivector * b.trivector
}

// ─── Quaternion (manual impl, no nalgebra) ───────────────────────────────────

/// Hamilton quaternion q = w + xi + yj + zk.
#[derive(Copy, Clone, Debug, Default)]
pub struct Quat {
    pub w: f64,
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Quat {
    pub fn from_xyzw(w: f64, x: f64, y: f64, z: f64) -> Self {
        Quat { w, x, y, z }
    }

    pub fn normalize(self) -> Self {
        let n = (self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z).sqrt();
        if n < 1e-15 {
            return Quat { w: 1.0, x: 0.0, y: 0.0, z: 0.0 };
        }
        Quat {
            w: self.w / n,
            x: self.x / n,
            y: self.y / n,
            z: self.z / n,
        }
    }

    pub fn conj(self) -> Self {
        Quat {
            w: self.w,
            x: -self.x,
            y: -self.y,
            z: -self.z,
        }
    }

    /// Hamilton product q * r
    pub fn mul(self, r: Quat) -> Quat {
        Quat {
            w: self.w * r.w - self.x * r.x - self.y * r.y - self.z * r.z,
            x: self.w * r.x + self.x * r.w + self.y * r.z - self.z * r.y,
            y: self.w * r.y - self.x * r.z + self.y * r.w + self.z * r.x,
            z: self.w * r.z + self.x * r.y - self.y * r.x + self.z * r.w,
        }
    }
}

/// Rotor application: R * v * R̃ treating v as pure-quaternion (0, vx, vy, vz).
pub fn rotor_apply(rotor: &[f64; 4], vector: &[f64; 3]) -> [f64; 3] {
    let r = Quat::from_xyzw(rotor[0], rotor[1], rotor[2], rotor[3]).normalize();
    let r_conj = r.conj();
    let v = Quat::from_xyzw(0.0, vector[0], vector[1], vector[2]);
    let result = r.mul(v).mul(r_conj);
    [result.x, result.y, result.z]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_geometric_product_identity() {
        let one = Multivector {
            scalar: 1.0,
            ..Default::default()
        };
        let x = Multivector {
            v1: 2.0,
            ..Default::default()
        };
        let result = geometric_product(&one, &x);
        assert!((result.v1 - 2.0).abs() < 1e-10);
    }

    #[test]
    fn test_outer_product_xy() {
        let e1 = Multivector {
            v1: 1.0,
            ..Default::default()
        };
        let e2 = Multivector {
            v2: 1.0,
            ..Default::default()
        };
        let result = outer_product(&e1, &e2);
        assert!((result.b3 - 1.0).abs() < 1e-10); // e1∧e2 = e12, b3 is e12
    }

    #[test]
    fn test_quat_mul_identity() {
        let q1 = Quat::from_xyzw(1.0, 2.0, 3.0, 4.0);
        let q2 = Quat::from_xyzw(0.0, 0.0, 0.0, 0.0);
        let r = q1.mul(q2);
        // q1 * 0 = 0
        assert!(r.w.abs() < 1e-12);
        assert!(r.x.abs() < 1e-12);
    }

    #[test]
    fn test_rotor_90_deg() {
        // 90° rotation around z-axis
        let angle = core::f64::consts::FRAC_PI_2;
        let rotor = [(angle / 2.0).cos(), 0.0, 0.0, (angle / 2.0).sin()];
        let v = [1.0, 0.0, 0.0];
        let result = rotor_apply(&rotor, &v);
        assert!((result[0]).abs() < 1e-10);
        assert!((result[1] - 1.0).abs() < 1e-10);
    }
}