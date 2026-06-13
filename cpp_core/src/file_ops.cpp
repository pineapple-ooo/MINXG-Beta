// file_ops.cpp — implementation
#include "file_ops.hpp"
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <glob.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace cpp_core::file_ops {

// ─── MappedFile ─────────────────────────────────────────────────────────────
MappedFile::MappedFile(const std::string& path, bool read_only) : path_(path) {
    int flags = O_RDONLY;
    fd_ = ::open(path.c_str(), flags);
    if (fd_ < 0) return;

    struct stat st;
    if (::fstat(fd_, &st) < 0) { ::close(fd_); fd_ = -1; return; }
    size_ = static_cast<std::size_t>(st.st_size);
    if (size_ == 0) { ::close(fd_); fd_ = -1; return; }

    int prot = PROT_READ;
    data_ = static_cast<std::byte*>(::mmap(nullptr, size_, prot, MAP_PRIVATE, fd_, 0));
    if (data_ == MAP_FAILED) { data_ = nullptr; ::close(fd_); fd_ = -1; return; }
}

MappedFile::~MappedFile() { close(); }

MappedFile::MappedFile(MappedFile&& o) noexcept
    : path_(std::move(o.path_)), data_(o.data_), size_(o.size_), fd_(o.fd_) {
    o.data_ = nullptr; o.size_ = 0; o.fd_ = -1;
}

MappedFile& MappedFile::operator=(MappedFile&& o) noexcept {
    if (this != &o) {
        close();
        path_ = std::move(o.path_);
        data_ = o.data_; o.data_ = nullptr;
        size_ = o.size_; o.size_ = 0;
        fd_ = o.fd_; o.fd_ = -1;
    }
    return *this;
}

void MappedFile::close() noexcept {
    if (data_) { ::munmap(data_, size_); data_ = nullptr; }
    if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
    size_ = 0;
}

bool MappedFile::is_open() const noexcept { return data_ != nullptr; }

bool MappedFile::unmapped(const std::string& path) {
    MappedFile f(path, true);
    return !f.is_open();  // unmapped = cannot map = doesn't exist or not readable
}

// ─── FileReader ─────────────────────────────────────────────────────────────
FileReader::FileReader(const std::string& path) : path_(path) {
    handle_ = std::fopen(path.c_str(), "rb");
}

FileReader::~FileReader() { close(); }

FileReader::FileReader(FileReader&& o) noexcept : handle_(o.handle_), path_(std::move(o.path_)) {
    o.handle_ = nullptr;
}

FileReader& FileReader::operator=(FileReader&& o) noexcept {
    if (this != &o) {
        close();
        handle_ = o.handle_; o.handle_ = nullptr;
        path_ = std::move(o.path_);
    }
    return *this;
}

bool FileReader::is_open() const noexcept { return handle_ != nullptr; }

void FileReader::close() noexcept {
    if (handle_) { std::fclose(static_cast<FILE*>(handle_)); handle_ = nullptr; }
}

std::size_t FileReader::read(ByteView buffer) noexcept {
    if (!handle_ || buffer.empty()) return 0;
    return std::fread(buffer.ptr, 1, buffer.len, static_cast<FILE*>(handle_));
}

bool FileReader::read_exact(ByteView buffer, std::size_t n) noexcept {
    if (!is_open() || buffer.len < n) return false;
    std::size_t total = 0;
    while (total < n) {
        std::size_t r = std::fread(buffer.ptr + total, 1, n - total, static_cast<FILE*>(handle_));
        if (r == 0) return total == n;
        total += r;
    }
    return true;
}

std::vector<std::byte> FileReader::read_all() noexcept {
    std::vector<std::byte> result;
    if (!is_open()) return result;
    std::fseek(static_cast<FILE*>(handle_), 0, SEEK_END);
    long len = std::ftell(static_cast<FILE*>(handle_));
    std::fseek(static_cast<FILE*>(handle_), 0, SEEK_SET);
    if (len <= 0) return result;
    result.resize(static_cast<std::size_t>(len));
    std::size_t r = std::fread(result.data(), 1, result.size(), static_cast<FILE*>(handle_));
    result.resize(r);
    return result;
}

// ─── FileWriter ──────────────────────────────────────────────────────────────
FileWriter::FileWriter(const std::string& path, Mode mode) : path_(path) {
    const char* m = (mode == Append) ? "ab" : "wb";
    handle_ = std::fopen(path.c_str(), m);
}

FileWriter::~FileWriter() { close(); }

FileWriter::FileWriter(FileWriter&& o) noexcept : handle_(o.handle_), path_(std::move(o.path_)) {
    o.handle_ = nullptr;
}

FileWriter& FileWriter::operator=(FileWriter&& o) noexcept {
    if (this != &o) {
        close();
        handle_ = o.handle_; o.handle_ = nullptr;
        path_ = std::move(o.path_);
    }
    return *this;
}

bool FileWriter::is_open() const noexcept { return handle_ != nullptr; }

void FileWriter::close() noexcept {
    if (handle_) { std::fclose(static_cast<FILE*>(handle_)); handle_ = nullptr; }
}

bool FileWriter::flush() noexcept {
    if (!handle_) return false;
    return std::fflush(static_cast<FILE*>(handle_)) == 0;
}

std::size_t FileWriter::write(ConstByteView data) noexcept {
    if (!handle_ || data.empty()) return 0;
    return std::fwrite(data.ptr, 1, data.len, static_cast<FILE*>(handle_));
}

std::size_t FileWriter::write(const std::string& s) noexcept {
    if (!handle_ || s.empty()) return 0;
    return std::fwrite(s.data(), 1, s.size(), static_cast<FILE*>(handle_));
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
std::vector<std::string> glob(const std::string& pattern) {
    std::vector<std::string> results;
    glob_t g{};
    if (::glob(pattern.c_str(), 0, nullptr, &g) == 0) {
        for (std::size_t i = 0; i < g.gl_pathc; ++i)
            results.emplace_back(g.gl_pathv[i]);
        ::globfree(&g);
    }
    return results;
}

bool exists(const std::string& path) {
    struct stat st; return ::stat(path.c_str(), &st) == 0;
}

bool is_file(const std::string& path) {
    struct stat st; return ::stat(path.c_str(), &st) == 0 && S_ISREG(st.st_mode);
}

bool is_dir(const std::string& path) {
    struct stat st; return ::stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
}

std::optional<std::uintmax_t> file_size(const std::string& path) {
    struct stat st;
    if (::stat(path.c_str(), &st) != 0) return std::nullopt;
    return static_cast<std::uintmax_t>(st.st_size);
}

bool copy_file(const std::string& src, const std::string& dst, bool overwrite) {
    if (!is_file(src)) return false;
    if (is_file(dst) && !overwrite) return false;

    FileReader in(src);
    if (!in.is_open()) return false;
    FileWriter out(dst, FileWriter::Truncate);
    if (!out.is_open()) return false;

    std::byte buf[8192];
    while (true) {
        std::size_t r = in.read({buf, sizeof(buf)});
        if (r == 0) break;
        if (out.write({buf, r}) != r) return false;
    }
    out.flush();
    return true;
}

bool remove_file(const std::string& path) {
    return ::unlink(path.c_str()) == 0 || ::remove(path.c_str()) == 0;
}

bool create_dir(const std::string& path) {
    return ::mkdir(path.c_str(), 0755) == 0;
}

bool remove_dir(const std::string& path) {
    return ::rmdir(path.c_str()) == 0;
}

std::string read_text(const std::string& path) {
    FileReader r(path);
    if (!r.is_open()) return {};
    auto bytes = r.read_all();
    return std::string(reinterpret_cast<const char*>(bytes.data()), bytes.size());
}

bool write_text(const std::string& path, const std::string& content) {
    FileWriter w(path, FileWriter::Truncate);
    if (!w.is_open()) return false;
    return w.write({reinterpret_cast<const std::byte*>(content.data()), content.size()}) == content.size();
}

}  // namespace cpp_core::file_ops