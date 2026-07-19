#include "base.hpp"
#include <algorithm>
#include <cstdlib>

namespace cpp_core {

// MemoryTracker implementation
MemoryTracker& MemoryTracker::instance() {
    static MemoryTracker tracker;
    return tracker;
}

MemoryStatsSnapshot MemoryTracker::snapshot() const {
    MemoryStatsSnapshot s;
    s.current_allocations = stats_.current_allocations.load();
    s.total_allocated     = stats_.total_allocated.load();
    s.total_freed         = stats_.total_freed.load();
    return s;
}

void MemoryTracker::record_allocation(size_t size) {
    stats_.current_allocations.fetch_add(1);
    stats_.total_allocated.fetch_add(size);
}

void MemoryTracker::record_deallocation(size_t size) {
    stats_.current_allocations.fetch_sub(1);
    stats_.total_freed.fetch_add(size);
}

void MemoryTracker::reset() {
    stats_.current_allocations = 0;
    stats_.total_allocated = 0;
    stats_.total_freed = 0;
}

// Base implementation
Base::Base() : name_("unnamed"), memory_size_(sizeof(Base)) {
    track_allocation(this, memory_size_);
}

Base::Base(const std::string& name) : name_(name), memory_size_(sizeof(Base)) {
    track_allocation(this, memory_size_);
}

Base::~Base() {
    if (alive_) {
        alive_ = false;
        track_deallocation(this);
        on_destroy();
    }
}

Base::Base(Base&& other) noexcept
    : name_(std::move(other.name_)),
      ref_count_(other.ref_count_.load()),
      alive_(other.alive_),
      memory_size_(other.memory_size_) {
    other.alive_ = false;
}

Base& Base::operator=(Base&& other) noexcept {
    if (this != &other) {
        if (alive_) {
            track_deallocation(this);
        }
        name_ = std::move(other.name_);
        ref_count_ = other.ref_count_.load();
        alive_ = other.alive_;
        memory_size_ = other.memory_size_;
        other.alive_ = false;
    }
    return *this;
}

void Base::retain() {
    if (!alive_) {
        throw InvalidStateError("Cannot retain dead object");
    }
    ref_count_.fetch_add(1);
}

void Base::release() {
    if (ref_count_.fetch_sub(1) == 1) {
        alive_ = false;
        track_deallocation(this);
        on_destroy();
        delete this;
    }
}

size_t Base::ref_count() const {
    return ref_count_.load();
}

size_t Base::memory_footprint() const {
    return memory_size_ + name_.capacity();
}

void Base::track_allocation(Base* ptr, size_t size) {
    if (ptr) {
        MemoryTracker::instance().record_allocation(size);
    }
}

void Base::track_deallocation(Base* ptr) {
    if (ptr) {
        MemoryTracker::instance().record_deallocation(ptr->memory_size_);
    }
}

} // namespace cpp_core