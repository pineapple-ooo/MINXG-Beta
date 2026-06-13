#ifndef CPP_CORE_BASE_HPP
#define CPP_CORE_BASE_HPP

#include <memory>
#include <atomic>
#include <string>
#include <stdexcept>

namespace cpp_core {

// Immutable snapshot returned to callers (no atomics, safe to copy)
struct MemoryStatsSnapshot {
    size_t current_allocations{0};
    size_t total_allocated{0};
    size_t total_freed{0};
};

// Internal tracker — atomics live here
struct MemoryStatsInternals {
    std::atomic<size_t> current_allocations{0};
    std::atomic<size_t> total_allocated{0};
    std::atomic<size_t> total_freed{0};
};

// Global memory tracker
class MemoryTracker {
public:
    static MemoryTracker& instance();

    MemoryStatsSnapshot snapshot() const;
    void record_allocation(size_t size);
    void record_deallocation(size_t size);
    void reset();

private:
    MemoryTracker() = default;
    ~MemoryTracker() = default;

    MemoryTracker(const MemoryTracker&) = delete;
    MemoryTracker& operator=(const MemoryTracker&) = delete;

    MemoryStatsInternals stats_;
};

// Base class implementing RAII and reference counting
class Base {
public:
    Base();
    explicit Base(const std::string& name);
    virtual ~Base();

    // Disable copy
    Base(const Base&) = delete;
    Base& operator=(const Base&) = delete;

    // Enable move
    Base(Base&& other) noexcept;
    Base& operator=(Base&& other) noexcept;

    // Reference counting
    void retain();
    void release();
    size_t ref_count() const;

    // Identity
    const std::string& name() const { return name_; }
    void set_name(const std::string& name) { name_ = name; }

    // Memory info
    size_t memory_footprint() const;

    // Check if alive
    bool is_alive() const { return alive_; }

protected:
    virtual void on_destroy() {}

private:
    std::string name_;
    std::atomic<size_t> ref_count_{1};
    bool alive_ = true;
    size_t memory_size_ = 0;

    static void track_allocation(Base* ptr, size_t size);
    static void track_deallocation(Base* ptr);
};

// Smart pointer type aliases
using BasePtr = std::unique_ptr<Base>;
using BaseSharedPtr = std::shared_ptr<Base>;
using BaseWeakPtr = std::weak_ptr<Base>;

// Exception types
class CoreException : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class MemoryError : public CoreException {
public:
    using CoreException::CoreException;
};

class InvalidStateError : public CoreException {
public:
    using CoreException::CoreException;
};

} // namespace cpp_core

#endif // CPP_CORE_BASE_HPP