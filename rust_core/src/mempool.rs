//! Arena-backed slotmap memory pool — zero-leak shared memory for FFI consumers.
//!
//! Design: pre-allocate a fixed-size arena, hand out `Slot` indices (never
//! pointers). Python/Go/Java consumers read/write slots via FFI, never see raw
//! pointers. No malloc/free in hot paths — all memory lives inside the arena.
//!
//! Safety: all bounds-checked. Oversized writes are clamped, not UB.

/// Maximum arena size (1 MiB — enough for 1000+ small operator payloads)
pub const ARENA_SIZE: usize = 1_048_576;

/// A slot within the arena — index + length, never a raw pointer.
#[repr(C)]
#[derive(Copy, Clone, Debug, Default)]
pub struct Slot {
    pub offset: u32,
    pub len: u32,
    pub used: u8,  // 0 = free, 1 = occupied
    pub tag: u8,   // user-defined category tag
}

/// The arena — fixed-size contiguous memory, managed via slotmap.
pub struct MemPool {
    arena: Vec<u8>,
    slots: Vec<Slot>,
    free_list: Vec<u32>,     // indices of freed slots
    allocated_bytes: usize,
    max_bytes: usize,
}

impl MemPool {
    /// Create a new memory pool with `capacity` bytes.
    pub fn new(capacity_bytes: usize) -> Self {
        let cap = capacity_bytes.min(ARENA_SIZE);
        MemPool {
            arena: vec![0u8; cap],
            slots: Vec::with_capacity(256),
            free_list: Vec::with_capacity(64),
            allocated_bytes: 0,
            max_bytes: cap,
        }
    }

    /// Allocate a new slot of `size` bytes. Returns slot index or usize::MAX.
    pub fn alloc(&mut self, size: usize) -> usize {
        if self.allocated_bytes + size > self.max_bytes {
            return usize::MAX; // out of memory
        }

        // Try free-list first
        if let Some(&idx) = self.free_list.last() {
            let slot_idx = idx as usize;
            if slot_idx < self.slots.len() && self.slots[slot_idx].len as usize >= size {
                self.free_list.pop();
                let offset = self.slots[slot_idx].offset;
                self.slots[slot_idx].len = size as u32;
                self.slots[slot_idx].used = 1;
                // zero the reused region
                for i in offset as usize..(offset as usize + size) {
                    self.arena[i] = 0;
                }
                return slot_idx;
            }
        }

        // Fresh allocation at end
        let offset = self.allocated_bytes;
        // zero the new region
        for i in offset..(offset + size).min(self.max_bytes) {
            self.arena[i] = 0;
        }
        self.allocated_bytes += size;

        let slot = Slot {
            offset: offset as u32,
            len: size as u32,
            used: 1,
            tag: 0,
        };
        self.slots.push(slot);
        self.slots.len() - 1
    }

    /// Free a slot by index. Returns true on success.
    pub fn free(&mut self, slot_idx: usize) -> bool {
        if slot_idx >= self.slots.len() { return false; }
        if self.slots[slot_idx].used == 0 { return false; }
        self.slots[slot_idx].used = 0;

        // Push onto free list for reuse
        if self.free_list.len() < 256 {
            self.free_list.push(slot_idx as u32);
        }
        true
    }

    /// Write data into a slot. Returns number of bytes actually written (clamped).
    pub fn write(&mut self, slot_idx: usize, data: &[u8]) -> usize {
        if slot_idx >= self.slots.len() || self.slots[slot_idx].used == 0 {
            return 0;
        }
        let offset = self.slots[slot_idx].offset as usize;
        let max = self.slots[slot_idx].len as usize;
        let n = data.len().min(max);
        self.arena[offset..offset + n].copy_from_slice(&data[..n]);
        n
    }

    /// Read data from a slot into a pre-allocated buffer. Returns bytes read.
    pub fn read(&self, slot_idx: usize, out: &mut [u8]) -> usize {
        if slot_idx >= self.slots.len() || self.slots[slot_idx].used == 0 {
            return 0;
        }
        let offset = self.slots[slot_idx].offset as usize;
        let len = self.slots[slot_idx].len as usize;
        let n = len.min(out.len());
        out[..n].copy_from_slice(&self.arena[offset..offset + n]);
        n
    }

    /// Stats: (slots_used, slots_free, bytes_used, bytes_free)
    pub fn stats(&self) -> (u32, u32, usize, usize) {
        let used_slots = self.slots.iter().filter(|s| s.used == 1).count() as u32;
        let free_slots = self.slots.len() as u32 - used_slots;
        (used_slots, free_slots, self.allocated_bytes, self.max_bytes - self.allocated_bytes)
    }
}

// ─── FFI exports (extern "C") ─────────────────────────────────────────────────

/// Create a pool (caller owns the returned opaque ptr). Returns null on OOM.
/// Python wraps this in a `ctypes.POINTER` and calls `mempool_free`.
#[no_mangle]
pub extern "C" fn mempool_create(capacity: usize) -> *mut MemPool {
    let pool = Box::new(MemPool::new(capacity));
    Box::into_raw(pool)
}

/// Destroy a pool. NULL-safe.
#[no_mangle]
pub extern "C" fn mempool_free(pool: *mut MemPool) {
    if pool.is_null() { return; }
    unsafe { drop(Box::from_raw(pool)); }
}

/// Allocate a slot. Returns slot_idx (usize::MAX on failure).
#[no_mangle]
pub extern "C" fn mempool_alloc(pool: *mut MemPool, size: usize) -> usize {
    if pool.is_null() { return usize::MAX; }
    unsafe { (*pool).alloc(size) }
}

/// Free a slot.
#[no_mangle]
pub extern "C" fn mempool_free_slot(pool: *mut MemPool, slot_idx: usize) -> i32 {
    if pool.is_null() { return -1; }
    unsafe {
        if (*pool).free(slot_idx) { 0 } else { -1 }
    }
}

/// Write bytes into a slot. Returns bytes written.
#[no_mangle]
pub extern "C" fn mempool_write(
    pool: *mut MemPool,
    slot_idx: usize,
    data: *const u8,
    data_len: usize,
) -> usize {
    if pool.is_null() || data.is_null() { return 0; }
    unsafe {
        let slice = std::slice::from_raw_parts(data, data_len);
        (*pool).write(slot_idx, slice)
    }
}

/// Read bytes from a slot. Returns bytes copied.
#[no_mangle]
pub extern "C" fn mempool_read(
    pool: *const MemPool,
    slot_idx: usize,
    out: *mut u8,
    out_cap: usize,
) -> usize {
    if pool.is_null() || out.is_null() { return 0; }
    unsafe {
        let out_slice = std::slice::from_raw_parts_mut(out, out_cap);
        (*pool).read(slot_idx, out_slice)
    }
}

/// Get pool stats: [used_slots, free_slots, used_bytes, free_bytes] as 4×u64.
#[no_mangle]
pub extern "C" fn mempool_stats(pool: *const MemPool, out: *mut u64) -> i32 {
    if pool.is_null() || out.is_null() { return -1; }
    unsafe {
        let (used_s, free_s, used_b, free_b) = (*pool).stats();
        let arr = std::slice::from_raw_parts_mut(out, 4);
        arr[0] = used_s as u64;
        arr[1] = free_s as u64;
        arr[2] = used_b as u64;
        arr[3] = free_b as u64;
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_alloc_write_read_free() {
        let mut pool = MemPool::new(1024);
        let idx = pool.alloc(64);
        assert!(idx < usize::MAX);

        let written = pool.write(idx, b"hello world");
        assert_eq!(written, 11);

        let mut buf = [0u8; 32];
        let read = pool.read(idx, &mut buf);
        assert_eq!(read, 11);
        assert_eq!(&buf[..11], b"hello world");

        assert!(pool.free(idx));
    }

    #[test]
    fn test_stats_empty() {
        let pool = MemPool::new(1024);
        let (used_s, free_s, used_b, free_b) = pool.stats();
        assert_eq!(used_s, 0);
        assert_eq!(used_b, 0);
        assert_eq!(free_b, 1024);
    }
}