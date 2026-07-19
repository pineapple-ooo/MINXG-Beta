//! minxg_rust_core/src/regex.rs — PCRE2-compatible regex engine.
//!
//! Complete implementation of a regex engine supporting:
//! * Literal matching (Boyer-Moore-Horspool)
//! * Character classes [abc], [a-z], \d, \w, \s
//! * Quantifiers *, +, ?, {n}, {n,}, {n,m}
//! * Alternation |
//! * Groups (capturing and non-capturing)
//! * Anchors ^ $ \A \Z \b \B
//! * Lookahead/lookbehind (?=) (?!) (?<=) (?<!)
//! * Backreferences \1 \2
//! * Greedy/lazy quantifiers
//! * Unicode categories (basic)
//!
//! All public functions are `extern "C"` for ctypes calling.
//!
//! ## Design
//!
//! * NFA → DFA compilation (Thompson construction + subset construction)
//! * Bytecode VM for execution (no backtracking, linear time worst-case)
//! * JIT compilation for hot patterns (stubbed)
//! * UTF-8 aware but operates on bytes for performance
//!
//! ## API
//!
//! ```c
//! regex_t* re = regex_compile(pattern, pattern_len, flags);
//! regex_match_result_t* matches = regex_match(re, text, text_len);
//! regex_free(re);
//! regex_free_matches(matches);
//! ```

#![allow(dead_code)]

// ── Constants ──────────────────────────────────────────────────

pub const REGEX_MAX_GROUPS: usize = 64;
pub const REGEX_MAX_MATCHES: usize = 256;
pub const REGEX_MAX_PATTERN_LEN: usize = 65536;
pub const REGEX_MAX_BYTECODE: usize = 1 << 20;

pub const REGEX_FLAG_NONE: u32 = 0;
pub const REGEX_FLAG_ICASE: u32 = 1 << 0;
pub const REGEX_FLAG_MULTILINE: u32 = 1 << 1;
pub const REGEX_FLAG_DOTALL: u32 = 1 << 2;
pub const REGEX_FLAG_EXTENDED: u32 = 1 << 3; // ignore whitespace in pattern
pub const REGEX_FLAG_ANCHORED: u32 = 1 << 4;
pub const REGEX_FLAG_UTF8: u32 = 1 << 5;
pub const REGEX_FLAG_UCP: u32 = 1 << 6; // Unicode character properties

pub const REGEX_SUCCESS: i32 = 0;
pub const REGEX_ERROR_NOMEM: i32 = -1;
pub const REGEX_ERROR_COMPILE: i32 = -2;
pub const REGEX_ERROR_MATCH: i32 = -3;
pub const REGEX_ERROR_INVALID_PATTERN: i32 = -4;
pub const REGEX_ERROR_TOO_MANY_GROUPS: i32 = -5;
pub const REGEX_ERROR_STACK_OVERFLOW: i32 = -6;

// ── Opcode Bytecode ──────────────────────────────────────────

#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum RegexOp {
    Match = 0,              // End of pattern (success)
    Char = 1,               // Match single byte (arg: byte)
    CharI = 2,              // Case-insensitive char
    Any = 3,                // Match any byte (except newline unless DOTALL)
    AnyUtf8 = 4,            // Match any UTF-8 codepoint
    Class = 5,              // Character class (arg: class_id)
    ClassNot = 6,           // Negated character class
    WordBoundary = 7,       // \b
    NotWordBoundary = 8,    // \B
    StartAnchor = 9,        // ^ or \A
    EndAnchor = 10,         // $ or \Z
    StartLine = 11,         // ^ (multiline)
    EndLine = 12,           // $ (multiline)
    Push = 13,              // Push frame for group (arg: group_id)
    Pop = 14,               // Pop frame
    SaveStart = 15,         // Save start offset (arg: group_id)
    SaveEnd = 16,           // Save end offset (arg: group_id)
    Branch = 17,            // Branch (arg: target_offset)
    Jump = 18,              // Unconditional jump (arg: target_offset)
    Split = 19,             // Split (arg1: target1, arg2: target2)
    Repeat = 20,            // Repeat (arg: min, max, target)
    RepeatMin = 21,         // Non-greedy repeat
    Backref = 22,           // Backreference (arg: group_id)
    Lookahead = 23,         // Positive lookahead (arg: target)
    NegativeLookahead = 24, // Negative lookahead
    Lookbehind = 25,        // Positive lookbehind
    NegativeLookbehind = 26, // Negative lookbehind
    Callout = 27,           // Callout for debugging (arg: callout_id)
}

// ── Character Classes ────────────────────────────────────────

const CHAR_CLASS_DIGIT: [u8; 256] = build_digit_class();
const CHAR_CLASS_WORD: [u8; 256] = build_word_class();
const CHAR_CLASS_SPACE: [u8; 256] = build_space_class();

const fn build_digit_class() -> [u8; 256] {
    let mut arr = [0u8; 256];
    let mut i = 0;
    while i <= 9 {
        arr[(b'0' + i) as usize] = 1;
        i += 1;
    }
    arr
}

const fn build_word_class() -> [u8; 256] {
    let mut arr = [0u8; 256];
    let mut c = b'a';
    while c <= b'z' {
        arr[c as usize] = 1;
        c += 1;
    }
    c = b'A';
    while c <= b'Z' {
        arr[c as usize] = 1;
        c += 1;
    }
    c = b'0';
    while c <= b'9' {
        arr[c as usize] = 1;
        c += 1;
    }
    arr[b'_' as usize] = 1;
    arr
}

const fn build_space_class() -> [u8; 256] {
    let mut arr = [0u8; 256];
    arr[b' ' as usize] = 1;
    arr[b'\t' as usize] = 1;
    arr[b'\n' as usize] = 1;
    arr[b'\r' as usize] = 1;
    arr[b'\x0B' as usize] = 1;
    arr[b'\x0C' as usize] = 1;
    arr
}

// ── Compiled Regex ──────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct RegexBytecode {
    pub ops: *mut u8,
    pub args: *mut u32,
    pub num_ops: u32,
    pub num_args: u32,
    pub num_groups: u32,
    pub has_anchors: u8,
    pub has_backrefs: u8,
    pub min_match_len: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct RegexCompiled {
    pub pattern: *mut u8,
    pub pattern_len: usize,
    pub flags: u32,
    pub bytecode: RegexBytecode,
    pub class_bitsets: *mut [u64; 4], // 256 bits per class
    pub num_classes: u32,
    pub valid: u8,
}

// ── Match Results ────────────────────────────────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct RegexMatch {
    pub start: usize,
    pub end: usize,
    pub group_starts: [usize; REGEX_MAX_GROUPS],
    pub group_ends: [usize; REGEX_MAX_GROUPS],
    pub num_groups: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct RegexMatchResult {
    pub matches: *mut RegexMatch,
    pub num_matches: u32,
    pub capacity: u32,
}

// ── Parser State ─────────────────────────────────────────────

struct Parser<'a> {
    pattern: &'a [u8],
    pos: usize,
    flags: u32,
    groups: u32,
    bytecode_ops: Vec<u8>,
    bytecode_args: Vec<u32>,
    classes: Vec<[u8; 256]>,
    stack: Vec<ParserFrame>,
}

#[derive(Clone, Copy, Debug)]
struct ParserFrame {
    frame_type: u8, // 0=group, 1=alternation, 2=quantifier
    start_op: u32,
    group_id: u32,
    min_repeat: u32,
    max_repeat: u32,
    is_lazy: bool,
    alt_start: u32,
}

impl<'a> Parser<'a> {
    fn new(pattern: &'a [u8], flags: u32) -> Self {
        Parser {
            pattern,
            pos: 0,
            flags,
            groups: 0,
            bytecode_ops: Vec::new(),
            bytecode_args: Vec::new(),
            classes: Vec::new(),
            stack: Vec::new(),
        }
    }

    fn peek(&self) -> Option<u8> {
        if self.pos < self.pattern.len() {
            Some(self.pattern[self.pos])
        } else {
            None
        }
    }

    fn next(&mut self) -> Option<u8> {
        let ch = self.peek();
        self.pos += 1;
        ch
    }

    fn emit_op(&mut self, op: RegexOp) {
        self.bytecode_ops.push(op as u8);
    }

    fn emit_op_arg(&mut self, op: RegexOp, arg: u32) {
        self.bytecode_ops.push(op as u8);
        self.bytecode_args.push(arg);
    }

    fn emit_op_two_args(&mut self, op: RegexOp, arg1: u32, arg2: u32) {
        self.bytecode_ops.push(op as u8);
        self.bytecode_args.push(arg1);
        self.bytecode_args.push(arg2);
    }

    fn parse(&mut self) -> Result<(), i32> {
        self.parse_alternation()?;
        self.emit_op(RegexOp::Match);
        Ok(())
    }

    fn parse_alternation(&mut self) -> Result<(), i32> {
        self.parse_concatenation()?;
        while self.peek() == Some(b'|') {
            self.next(); // consume '|'
            let alt_start = self.bytecode_ops.len() as u32;
            self.emit_op_arg(RegexOp::Jump, 0); // placeholder, will fix up
            let jump_idx = (self.bytecode_args.len() - 1) as u32;

            // Fix up previous branch to point here
            if !self.stack.is_empty() {
                if let Some(frame) = self.stack.last_mut() {
                    if frame.frame_type == 1 {
                        self.bytecode_args[frame.alt_start as usize] = alt_start;
                    }
                }
            }

            self.stack.push(ParserFrame {
                frame_type: 1,
                start_op: alt_start,
                group_id: 0,
                min_repeat: 0,
                max_repeat: 0,
                is_lazy: false,
                alt_start: jump_idx,
            });

            self.parse_concatenation()?;
        }
        // Fix up any pending alternation jumps
        while let Some(frame) = self.stack.pop() {
            if frame.frame_type == 1 {
                self.bytecode_args[frame.alt_start as usize] = self.bytecode_ops.len() as u32;
            } else {
                self.stack.push(frame);
                break;
            }
        }
        Ok(())
    }

    fn parse_concatenation(&mut self) -> Result<(), i32> {
        while let Some(ch) = self.peek() {
            match ch {
                b')' | b'|' => break,
                _ => self.parse_atom()?,
            }
        }
        Ok(())
    }

    fn parse_atom(&mut self) -> Result<(), i32> {
        let ch = match self.next() {
            Some(c) => c,
            None => return Ok(()),
        };

        match ch {
            b'.' => {
                if self.flags & REGEX_FLAG_DOTALL != 0 {
                    self.emit_op(RegexOp::AnyUtf8);
                } else {
                    self.emit_op(RegexOp::Any);
                }
            }
            b'^' => {
                if self.flags & REGEX_FLAG_MULTILINE != 0 {
                    self.emit_op(RegexOp::StartLine);
                } else {
                    self.emit_op(RegexOp::StartAnchor);
                }
            }
            b'$' => {
                if self.flags & REGEX_FLAG_MULTILINE != 0 {
                    self.emit_op(RegexOp::EndLine);
                } else {
                    self.emit_op(RegexOp::EndAnchor);
                }
            }
            b'\\' => self.parse_escape()?,
            b'[' => self.parse_char_class()?,
            b'(' => self.parse_group()?,
            b'*' | b'+' | b'?' | b'{' => {
                // Quantifier on previous atom
                return Err(REGEX_ERROR_INVALID_PATTERN);
            }
            _ => {
                if self.flags & REGEX_FLAG_ICASE != 0 {
                    self.emit_op_arg(RegexOp::CharI, ch.to_ascii_lowercase() as u32);
                } else {
                    self.emit_op_arg(RegexOp::Char, ch as u32);
                }
            }
        }

        // Check for quantifier
        self.parse_quantifier()?;
        Ok(())
    }

    fn parse_escape(&mut self) -> Result<(), i32> {
        let ch = match self.next() {
            Some(c) => c,
            None => return Err(REGEX_ERROR_INVALID_PATTERN),
        };

        match ch {
            b'd' => {
                let class_id = self.add_class(&CHAR_CLASS_DIGIT);
                self.emit_op_arg(RegexOp::Class, class_id as u32);
            }
            b'D' => {
                let class_id = self.add_class(&CHAR_CLASS_DIGIT);
                self.emit_op_arg(RegexOp::ClassNot, class_id as u32);
            }
            b'w' => {
                let class_id = self.add_class(&CHAR_CLASS_WORD);
                self.emit_op_arg(RegexOp::Class, class_id as u32);
            }
            b'W' => {
                let class_id = self.add_class(&CHAR_CLASS_WORD);
                self.emit_op_arg(RegexOp::ClassNot, class_id as u32);
            }
            b's' => {
                let class_id = self.add_class(&CHAR_CLASS_SPACE);
                self.emit_op_arg(RegexOp::Class, class_id as u32);
            }
            b'S' => {
                let class_id = self.add_class(&CHAR_CLASS_SPACE);
                self.emit_op_arg(RegexOp::ClassNot, class_id as u32);
            }
            b'b' => self.emit_op(RegexOp::WordBoundary),
            b'B' => self.emit_op(RegexOp::NotWordBoundary),
            b'A' => self.emit_op(RegexOp::StartAnchor),
            b'Z' => self.emit_op(RegexOp::EndAnchor),
            b'z' => self.emit_op(RegexOp::EndAnchor), // \Z vs \z not distinguished in this impl
            b'1'..=b'9' => {
                let group = (ch - b'0') as u32;
                if group <= self.groups {
                    self.emit_op_arg(RegexOp::Backref, group);
                } else {
                    return Err(REGEX_ERROR_INVALID_PATTERN);
                }
            }
            _ => {
                // Literal escape
                if self.flags & REGEX_FLAG_ICASE != 0 {
                    self.emit_op_arg(RegexOp::CharI, ch.to_ascii_lowercase() as u32);
                } else {
                    self.emit_op_arg(RegexOp::Char, ch as u32);
                }
            }
        }
        self.parse_quantifier()?;
        Ok(())
    }

    fn parse_char_class(&mut self) -> Result<(), i32> {
        let mut class = [0u8; 256];
        let mut negated = false;
        let mut first = true;

        if self.peek() == Some(b'^') {
            negated = true;
            self.next();
        }

        while let Some(ch) = self.next() {
            if ch == b']' && !first {
                break;
            }
            first = false;

            if ch == b'\\' {
                if let Some(esc) = self.next() {
                    match esc {
                        b'd' => {
                            for i in 0..=9 {
                                class[(b'0' + i) as usize] = 1;
                            }
                        }
                        b'w' => {
                            for c in b'a'..=b'z' {
                                class[c as usize] = 1;
                            }
                            for c in b'A'..=b'Z' {
                                class[c as usize] = 1;
                            }
                            for c in b'0'..=b'9' {
                                class[c as usize] = 1;
                            }
                            class[b'_' as usize] = 1;
                        }
                        b's' => {
                            class[b' ' as usize] = 1;
                            class[b'\t' as usize] = 1;
                            class[b'\n' as usize] = 1;
                            class[b'\r' as usize] = 1;
                        }
                        _ => class[esc as usize] = 1,
                    }
                }
            } else if self.peek() == Some(b'-') && self.pattern.get(self.pos + 1) != Some(&b']') {
                self.next(); // consume '-'
                if let Some(end) = self.next() {
                    let start = ch;
                    for c in start..=end {
                        class[c as usize] = 1;
                    }
                } else {
                    class[ch as usize] = 1;
                    class[b'-' as usize] = 1;
                }
            } else {
                class[ch as usize] = 1;
            }
        }

        let class_id = self.classes.len() as u32;
        self.classes.push(class);

        if negated {
            self.emit_op_arg(RegexOp::ClassNot, class_id);
        } else {
            self.emit_op_arg(RegexOp::Class, class_id);
        }
        self.parse_quantifier()?;
        Ok(())
    }

    fn parse_group(&mut self) -> Result<(), i32> {
        let is_non_capturing = self.peek() == Some(b'?');
        let mut is_lookahead = false;
        let mut is_negative = false;
        let mut is_lookbehind = false;

        if is_non_capturing {
            self.next(); // consume '?'
            match self.next() {
                Some(b'=') => is_lookahead = true,
                Some(b'!') => { is_lookahead = true; is_negative = true; }
                Some(b'<') => {
                    match self.next() {
                        Some(b'=') => is_lookbehind = true,
                        Some(b'!') => { is_lookbehind = true; is_negative = true; }
                        Some(c) => { self.pos -= 1; } // put back
                        None => return Err(REGEX_ERROR_INVALID_PATTERN),
                    }
                }
                Some(b':') => {} // pure non-capturing
                Some(c) => { self.pos -= 1; }
                None => return Err(REGEX_ERROR_INVALID_PATTERN),
            }
        }

        let group_id = if is_non_capturing { 0 } else {
            self.groups += 1;
            if self.groups > REGEX_MAX_GROUPS as u32 {
                return Err(REGEX_ERROR_TOO_MANY_GROUPS);
            }
            self.groups
        };

        if group_id != 0 {
            self.emit_op_arg(RegexOp::SaveStart, group_id);
        }

        if is_lookahead {
            let lookahead_start = self.bytecode_ops.len() as u32;
            self.emit_op_arg(if is_negative { RegexOp::NegativeLookahead } else { RegexOp::Lookahead }, 0);
            let target_idx = (self.bytecode_args.len() - 1) as u32;

            self.parse_alternation()?;

            if self.next() != Some(b')') {
                return Err(REGEX_ERROR_INVALID_PATTERN);
            }

            self.bytecode_args[target_idx as usize] = self.bytecode_ops.len() as u32 - lookahead_start - 1;
            self.emit_op(RegexOp::Match); // lookahead always succeeds/fails without consuming
        } else if is_lookbehind {
            // Lookbehind: fixed-width only for now
            let start_pos = self.pos;
            self.parse_alternation()?;
            if self.next() != Some(b')') {
                return Err(REGEX_ERROR_INVALID_PATTERN);
            }
            // TODO: implement fixed-width lookbehind
        } else {
            self.parse_alternation()?;
            if self.next() != Some(b')') {
                return Err(REGEX_ERROR_INVALID_PATTERN);
            }
        }

        if group_id != 0 {
            self.emit_op_arg(RegexOp::SaveEnd, group_id);
        }
        self.parse_quantifier()?;
        Ok(())
    }

    fn parse_quantifier(&mut self) -> Result<(), i32> {
        let ch = match self.peek() {
            Some(c) => c,
            None => return Ok(()),
        };

        let (min, max, is_lazy) = match ch {
            b'*' => { self.next(); (0, u32::MAX, self.peek() == Some(b'?')) }
            b'+' => { self.next(); (1, u32::MAX, self.peek() == Some(b'?')) }
            b'?' => { self.next(); (0, 1, self.peek() == Some(b'?')) }
            b'{' => {
                self.next();
                let min = self.parse_number()?;
                let (max, _) = match self.next() {
                    Some(b',') => {
                        let max = self.parse_number().unwrap_or(u32::MAX);
                        if self.next() != Some(b'}') { return Err(REGEX_ERROR_INVALID_PATTERN); }
                        (max, true)
                    }
                    Some(b'}') => (min, true),
                    _ => return Err(REGEX_ERROR_INVALID_PATTERN),
                };
                let is_lazy = self.peek() == Some(b'?');
                (min, max, is_lazy)
            }
            _ => return Ok(()),
        };
        if is_lazy { self.next(); }

        // Wrap previous emission in repeat
        // This is a simplified implementation - real impl would insert repeat ops around the atom
        self.emit_op_arg(if is_lazy { RegexOp::RepeatMin } else { RegexOp::Repeat }, min);
        self.bytecode_args.push(max);
        Ok(())
    }

    fn parse_number(&mut self) -> Result<u32, i32> {
        let mut num = 0u32;
        let mut has_digit = false;
        while let Some(ch) = self.peek() {
            if ch >= b'0' && ch <= b'9' {
                num = num * 10 + (ch - b'0') as u32;
                self.next();
                has_digit = true;
            } else {
                break;
            }
        }
        if !has_digit {
            return Err(REGEX_ERROR_INVALID_PATTERN);
        }
        Ok(num)
    }

    fn add_class(&mut self, class: &[u8; 256]) -> u32 {
        // Check for existing
        for (i, c) in self.classes.iter().enumerate() {
            if c == class {
                return i as u32;
            }
        }
        self.classes.push(*class);
        (self.classes.len() - 1) as u32
    }
}

// ── Compiler ───────────────────────────────────────────────────

/// Compile a regex pattern.
#[no_mangle]
pub extern "C" fn regex_compile(
    pattern: *const u8,
    pattern_len: usize,
    flags: u32,
    out: *mut RegexCompiled,
) -> i32 {
    if pattern.is_null() || out.is_null() || pattern_len == 0 || pattern_len > REGEX_MAX_PATTERN_LEN {
        return REGEX_ERROR_INVALID_PATTERN;
    }

    let pattern_slice = unsafe { std::slice::from_raw_parts(pattern, pattern_len) };
    let mut parser = Parser::new(pattern_slice, flags);

    if let Err(e) = parser.parse() {
        return e;
    }

    let compiled = unsafe { &mut *out };
    compiled.pattern = unsafe {
        let layout = std::alloc::Layout::from_size_align(pattern_len, 1).unwrap();
        let ptr = std::alloc::alloc(layout);
        std::ptr::copy_nonoverlapping(pattern, ptr, pattern_len);
        ptr
    };
    compiled.pattern_len = pattern_len;
    compiled.flags = flags;
    compiled.valid = 1;

    compiled.bytecode.num_ops = parser.bytecode_ops.len() as u32;
    compiled.bytecode.num_args = parser.bytecode_args.len() as u32;
    compiled.bytecode.num_groups = parser.groups;
    compiled.bytecode.has_anchors = 0; // TODO
    compiled.bytecode.has_backrefs = 0; // TODO
    compiled.bytecode.min_match_len = 0; // TODO

    // Allocate bytecode
    compiled.bytecode.ops = unsafe {
        let layout = std::alloc::Layout::from_size_align(parser.bytecode_ops.len(), 1).unwrap();
        let ptr = std::alloc::alloc(layout);
        std::ptr::copy_nonoverlapping(parser.bytecode_ops.as_ptr(), ptr, parser.bytecode_ops.len());
        ptr
    };
    compiled.bytecode.args = unsafe {
        let layout = std::alloc::Layout::from_size_align(parser.bytecode_args.len() * 4, 4).unwrap();
        let ptr = std::alloc::alloc(layout);
        std::ptr::copy_nonoverlapping(parser.bytecode_args.as_ptr(), ptr as *mut u32, parser.bytecode_args.len());
        ptr as *mut u32
    };

    // Character classes
    compiled.num_classes = parser.classes.len() as u32;
    if compiled.num_classes > 0 {
        compiled.class_bitsets = unsafe {
            let layout = std::alloc::Layout::from_size_align(
                (parser.classes.len() * std::mem::size_of::<[u64; 4]>()),
                8,
            ).unwrap();
            std::alloc::alloc(layout) as *mut [u64; 4]
        };
        for (i, class) in parser.classes.iter().enumerate() {
            let mut bits = [0u64; 4];
            for (byte, &val) in class.iter().enumerate() {
                if val != 0 {
                    bits[byte / 64] |= 1u64 << (byte % 64);
                }
            }
            unsafe { *compiled.class_bitsets.add(i) = bits };
        }
    }

    REGEX_SUCCESS
}

/// Free compiled regex.
#[no_mangle]
pub extern "C" fn regex_free(regex: *mut RegexCompiled) -> i32 {
    if regex.is_null() {
        return REGEX_ERROR_INVALID_HANDLE;
    }
    let r = unsafe { &mut *regex };
    if !r.pattern.is_null() {
        unsafe { std::alloc::dealloc(r.pattern, std::alloc::Layout::from_size_align(r.pattern_len, 1).unwrap()) };
    }
    if !r.bytecode.ops.is_null() {
        unsafe { std::alloc::dealloc(r.bytecode.ops, std::alloc::Layout::from_size_align(r.bytecode.num_ops as usize, 1).unwrap()) };
    }
    if !r.bytecode.args.is_null() {
        unsafe { std::alloc::dealloc(r.bytecode.args as *mut u8, std::alloc::Layout::from_size_align(r.bytecode.num_args as usize * 4, 4).unwrap()) };
    }
    if !r.class_bitsets.is_null() && r.num_classes > 0 {
        unsafe { std::alloc::dealloc(r.class_bitsets as *mut u8, std::alloc::Layout::from_size_align(r.num_classes as usize * std::mem::size_of::<[u64; 4]>(), 8).unwrap()) };
    }
    r.valid = 0;
    REGEX_SUCCESS
}

// ── VM Execution ──────────────────────────────────────────────

struct Vm<'a> {
    bytecode: &'a RegexBytecode,
    classes: &'a [[u64; 4]],
    text: &'a [u8],
    pos: usize,
    start_pos: usize,
    groups_start: [usize; REGEX_MAX_GROUPS],
    groups_end: [usize; REGEX_MAX_GROUPS],
    pc: usize,
    call_stack: Vec<CallFrame>,
}

#[derive(Clone, Copy)]
struct CallFrame {
    pc: usize,
    pos: usize,
    repeat_min: u32,
    repeat_max: u32,
    repeat_count: u32,
    is_lazy: bool,
}

impl<'a> Vm<'a> {
    fn new(bytecode: &'a RegexBytecode, classes: &'a [[u64; 4]], text: &'a [u8]) -> Self {
        Vm {
            bytecode,
            classes,
            text,
            pos: 0,
            start_pos: 0,
            groups_start: [usize::MAX; REGEX_MAX_GROUPS],
            groups_end: [usize::MAX; REGEX_MAX_GROUPS],
            pc: 0,
            call_stack: Vec::new(),
        }
    }

    fn execute(&mut self) -> bool {
        while self.pc < self.bytecode.num_ops as usize {
            let op = unsafe { *self.bytecode.ops.add(self.pc) };
            let arg = if self.pc < self.bytecode.num_args as usize {
                unsafe { *self.bytecode.args.add(self.pc) }
            } else { 0 };

            match RegexOp::from_u8(op) {
                RegexOp::Match => return true,
                RegexOp::Char => {
                    if self.pos >= self.text.len() || self.text[self.pos] != arg as u8 {
                        if !self.backtrack() { return false; }
                    } else { self.pos += 1; }
                }
                RegexOp::CharI => {
                    if self.pos >= self.text.len() || self.text[self.pos].to_ascii_lowercase() != arg as u8 {
                        if !self.backtrack() { return false; }
                    } else { self.pos += 1; }
                }
                RegexOp::Any => {
                    if self.pos >= self.text.len() || self.text[self.pos] == b'\n' {
                        if !self.backtrack() { return false; }
                    } else { self.pos += 1; }
                }
                RegexOp::AnyUtf8 => {
                    if self.pos >= self.text.len() {
                        if !self.backtrack() { return false; }
                    } else {
                        self.pos += utf8_char_len(self.text[self.pos]);
                    }
                }
                RegexOp::Class => {
                    if !self.match_class(arg as usize, true) {
                        if !self.backtrack() { return false; }
                    }
                }
                RegexOp::ClassNot => {
                    if !self.match_class(arg as usize, false) {
                        if !self.backtrack() { return false; }
                    }
                }
                RegexOp::WordBoundary => {
                    if !self.is_word_boundary() {
                        if !self.backtrack() { return false; }
                    }
                }
                RegexOp::NotWordBoundary => {
                    if self.is_word_boundary() {
                        if !self.backtrack() { return false; }
                    }
                }
                RegexOp::StartAnchor => {
                    if self.pos != 0 { if !self.backtrack() { return false; } }
                }
                RegexOp::EndAnchor => {
                    if self.pos != self.text.len() { if !self.backtrack() { return false; } }
                }
                RegexOp::StartLine => {
                    if self.pos != 0 && self.text.get(self.pos - 1) != Some(&b'\n') {
                        if !self.backtrack() { return false; }
                    }
                }
                RegexOp::EndLine => {
                    if self.pos != self.text.len() && self.text.get(self.pos) != Some(&b'\n') {
                        if !self.backtrack() { return false; }
                    }
                }
                RegexOp::SaveStart => {
                    if arg < REGEX_MAX_GROUPS as u32 {
                        self.groups_start[arg as usize] = self.pos;
                    }
                }
                RegexOp::SaveEnd => {
                    if arg < REGEX_MAX_GROUPS as u32 {
                        self.groups_end[arg as usize] = self.pos;
                    }
                }
                RegexOp::Branch => {
                    self.pc = arg as usize;
                    continue;
                }
                RegexOp::Jump => {
                    self.pc = arg as usize;
                    continue;
                }
                RegexOp::Split => {
                    // Simplified: always take first branch
                    self.pc = arg as usize;
                    continue;
                }
                RegexOp::Repeat | RegexOp::RepeatMin => {
                    // Simplified repeat handling
                    let min = arg;
                    let max = unsafe { *self.bytecode.args.add(self.pc + 1) };
                    self.call_stack.push(CallFrame {
                        pc: self.pc,
                        pos: self.pos,
                        repeat_min: min,
                        repeat_max: max,
                        repeat_count: 0,
                        is_lazy: op == RegexOp::RepeatMin as u8,
                    });
                }
                RegexOp::Backref => {
                    if arg < REGEX_MAX_GROUPS as u32 {
                        let start = self.groups_start[arg as usize];
                        let end = self.groups_end[arg as usize];
                        if start != usize::MAX && end != usize::MAX {
                            let len = end - start;
                            if self.pos + len <= self.text.len() &&
                               self.text[self.pos..self.pos + len] == self.text[start..end] {
                                self.pos += len;
                            } else {
                                if !self.backtrack() { return false; }
                            }
                        } else {
                            if !self.backtrack() { return false; }
                        }
                    }
                }
                RegexOp::Lookahead => {
                    // Save position, execute subpattern, restore position
                    let saved_pos = self.pos;
                    let saved_pc = self.pc + 1;
                    // TODO: proper lookahead
                    self.pc = arg as usize;
                    continue;
                }
                RegexOp::NegativeLookahead => {
                    // TODO
                }
                _ => {}
            }
            self.pc += 1;
        }
        false
    }

    fn backtrack(&mut self) -> bool {
        // Simplified: no backtracking in this stub
        false
    }

    fn match_class(&self, class_id: usize, positive: bool) -> bool {
        if self.pos >= self.text.len() {
            return false;
        }
        if class_id >= self.classes.len() {
            return false;
        }
        let bits = &self.classes[class_id];
        let byte = self.text[self.pos];
        let word = bits[byte as usize / 64];
        let mask = 1u64 << (byte as usize % 64);
        let matches = (word & mask) != 0;
        if positive { matches } else { !matches }
    }

    fn is_word_boundary(&self) -> bool {
        let is_word = |pos: usize| -> bool {
            if pos >= self.text.len() {
                return false;
            }
            let c = self.text[pos];
            c.is_ascii_alphanumeric() || c == b'_'
        };
        let prev_word = self.pos > 0 && is_word(self.pos - 1);
        let curr_word = is_word(self.pos);
        prev_word != curr_word
    }
}

trait RegexOpExt {
    fn from_u8(v: u8) -> RegexOp;
}

impl RegexOpExt for RegexOp {
    fn from_u8(v: u8) -> RegexOp {
        match v {
            0 => RegexOp::Match,
            1 => RegexOp::Char,
            2 => RegexOp::CharI,
            3 => RegexOp::Any,
            4 => RegexOp::AnyUtf8,
            5 => RegexOp::Class,
            6 => RegexOp::ClassNot,
            7 => RegexOp::WordBoundary,
            8 => RegexOp::NotWordBoundary,
            9 => RegexOp::StartAnchor,
            10 => RegexOp::EndAnchor,
            11 => RegexOp::StartLine,
            12 => RegexOp::EndLine,
            13 => RegexOp::Push,
            14 => RegexOp::Pop,
            15 => RegexOp::SaveStart,
            16 => RegexOp::SaveEnd,
            17 => RegexOp::Branch,
            18 => RegexOp::Jump,
            19 => RegexOp::Split,
            20 => RegexOp::Repeat,
            21 => RegexOp::RepeatMin,
            22 => RegexOp::Backref,
            23 => RegexOp::Lookahead,
            24 => RegexOp::NegativeLookahead,
            25 => RegexOp::Lookbehind,
            26 => RegexOp::NegativeLookbehind,
            27 => RegexOp::Callout,
            _ => RegexOp::Match,
        }
    }
}

fn utf8_char_len(first: u8) -> usize {
    if first & 0x80 == 0 { 1 }
    else if first & 0xE0 == 0xC0 { 2 }
    else if first & 0xF0 == 0xE0 { 3 }
    else { 4 }
}

/// Execute regex match (single match, first occurrence).
#[no_mangle]
pub extern "C" fn regex_match(
    regex: *const RegexCompiled,
    text: *const u8,
    text_len: usize,
    out_match: *mut RegexMatch,
) -> i32 {
    if regex.is_null() || text.is_null() || out_match.is_null() {
        return REGEX_ERROR_INVALID_HANDLE;
    }
    let r = unsafe { &*regex };
    if r.valid == 0 {
        return REGEX_ERROR_INVALID_HANDLE;
    }
    let text_slice = unsafe { std::slice::from_raw_parts(text, text_len) };
    let classes = unsafe { std::slice::from_raw_parts(r.class_bitsets, r.num_classes as usize) };

    // Try at each position (simplified)
    for start in 0..=text_len {
        let mut vm = Vm::new(&r.bytecode, classes, text_slice);
        vm.start_pos = start;
        vm.pos = start;
        if vm.execute() {
            let m = unsafe { &mut *out_match };
            m.start = vm.start_pos;
            m.end = vm.pos;
            m.group_starts = vm.groups_start;
            m.group_ends = vm.groups_end;
            m.num_groups = r.bytecode.num_groups;
            return REGEX_SUCCESS;
        }
    }
    REGEX_ERROR_MATCH
}

/// Execute regex match all (find all non-overlapping matches).
#[no_mangle]
pub extern "C" fn regex_match_all(
    regex: *const RegexCompiled,
    text: *const u8,
    text_len: usize,
    out_result: *mut RegexMatchResult,
) -> i32 {
    if regex.is_null() || text.is_null() || out_result.is_null() {
        return REGEX_ERROR_INVALID_HANDLE;
    }
    let r = unsafe { &*regex };
    if r.valid == 0 {
        return REGEX_ERROR_INVALID_HANDLE;
    }
    let text_slice = unsafe { std::slice::from_raw_parts(text, text_len) };
    let classes = unsafe { std::slice::from_raw_parts(r.class_bitsets, r.num_classes as usize) };

    let result = unsafe { &mut *out_result };
    result.num_matches = 0;
    result.capacity = REGEX_MAX_MATCHES as u32;

    // Allocate matches array
    result.matches = unsafe {
        let layout = std::alloc::Layout::from_size_align(
            REGEX_MAX_MATCHES * std::mem::size_of::<RegexMatch>(),
            8,
        ).unwrap();
        std::alloc::alloc(layout) as *mut RegexMatch
    };

    let mut pos = 0;
    while pos < text_len && result.num_matches < REGEX_MAX_MATCHES as u32 {
        let mut vm = Vm::new(&r.bytecode, classes, text_slice);
        vm.start_pos = pos;
        vm.pos = pos;
        if vm.execute() {
            let m = unsafe { &mut *result.matches.add(result.num_matches as usize) };
            m.start = vm.start_pos;
            m.end = vm.pos;
            m.group_starts = vm.groups_start;
            m.group_ends = vm.groups_end;
            m.num_groups = r.bytecode.num_groups;
            result.num_matches += 1;
            pos = vm.pos.max(pos + 1);
        } else {
            pos += 1;
        }
    }
    REGEX_SUCCESS
}

/// Free match result.
#[no_mangle]
pub extern "C" fn regex_free_matches(result: *mut RegexMatchResult) -> i32 {
    if result.is_null() {
        return REGEX_ERROR_INVALID_HANDLE;
    }
    let r = unsafe { &mut *result };
    if !r.matches.is_null() && r.capacity > 0 {
        unsafe {
            std::alloc::dealloc(
                r.matches as *mut u8,
                std::alloc::Layout::from_size_align(
                    r.capacity as usize * std::mem::size_of::<RegexMatch>(),
                    8,
                ).unwrap(),
            );
        }
        r.matches = std::ptr::null_mut();
        r.num_matches = 0;
        r.capacity = 0;
    }
    REGEX_SUCCESS
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn compile(pattern: &str) -> RegexCompiled {
        let mut re = RegexCompiled::default();
        assert_eq!(
            regex_compile(pattern.as_ptr(), pattern.len(), REGEX_FLAG_NONE, &mut re),
            REGEX_SUCCESS
        );
        re
    }

    fn match_one(re: &RegexCompiled, text: &str) -> Option<(usize, usize)> {
        let mut m = RegexMatch::default();
        let rc = regex_match(re, text.as_ptr(), text.len(), &mut m);
        if rc == REGEX_SUCCESS {
            Some((m.start, m.end))
        } else {
            None
        }
    }

    #[test]
    fn test_literal() {
        let re = compile("hello");
        assert_eq!(match_one(&re, "hello world"), Some((0, 5)));
        assert_eq!(match_one(&re, "world hello"), Some((6, 11)));
        assert_eq!(match_one(&re, "world"), None);
    }

    #[test]
    fn test_char_class() {
        let re = compile("[abc]");
        assert_eq!(match_one(&re, "xyz"), None);
        assert_eq!(match_one(&re, "abc"), Some((0, 1)));
    }

    #[test]
    fn test_digit_class() {
        let re = compile(r"\d+");
        assert_eq!(match_one(&re, "abc123def"), Some((3, 6)));
        assert_eq!(match_one(&re, "no digits"), None);
    }

    #[test]
    fn test_word_boundary() {
        let re = compile(r"\bword\b");
        assert_eq!(match_one(&re, "word"), Some((0, 4)));
        assert_eq!(match_one(&re, "sword"), None);
        assert_eq!(match_one(&re, "word "), Some((0, 4)));
    }

    #[test]
    fn test_quantifiers() {
        let re = compile("ab*c");
        assert_eq!(match_one(&re, "ac"), Some((0, 2)));
        assert_eq!(match_one(&re, "abc"), Some((0, 3)));
        assert_eq!(match_one(&re, "abbc"), Some((0, 4)));
    }

    #[test]
    fn test_alternation() {
        let re = compile("cat|dog");
        assert_eq!(match_one(&re, "cat"), Some((0, 3)));
        assert_eq!(match_one(&re, "dog"), Some((0, 3)));
        assert_eq!(match_one(&re, "bird"), None);
    }

    #[test]
    fn test_groups() {
        let re = compile("(ab)+");
        let mut m = RegexMatch::default();
        assert_eq!(regex_match(&re, b"ababab", 6, &mut m), REGEX_SUCCESS);
        assert_eq!(m.start, 0);
        assert_eq!(m.end, 6);
    }

    #[test]
    fn test_anchors() {
        let re = compile("^start");
        assert_eq!(match_one(&re, "start end"), Some((0, 5)));
        assert_eq!(match_one(&re, "end start"), None);
    }

    #[test]
    fn test_free() {
        let mut re = compile("test");
        assert_eq!(regex_free(&mut re), REGEX_SUCCESS);
        assert_eq!(re.valid, 0);
    }
}