"""
Native Syntax Highlighting for C++, C, Go, Shell
Pure Python implementation — no Pygments or external dependencies required.

Usage:
    from multiligua_cli.syntax import highlight_cpp, highlight_c, highlight_go, highlight_shell
    highlighted = highlight_cpp(code)
"""

import re
from typing import Dict, Optional

# ANSI color codes
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Syntax element colors
    KEYWORD = "\033[38;5;147m"    # Magenta/purple for keywords
    TYPE = "\033[38;5;75m"       # Cyan for types
    STRING = "\033[38;5;114m"    # Green for strings
    COMMENT = "\033[38;5;241m"   # Gray for comments
    NUMBER = "\033[38;5;173m"    # Orange for numbers
    FUNCTION = "\033[38;5;147m"  # Magenta for functions
    PREPROC = "\033[38;5;186m"   # Yellow for preprocessor/directives
    OPERATOR = "\033[38;5;180m"  # Brown for operators
    BUILTIN = "\033[38;5;147m"   # Magenta for builtins


def _build_patterns(lang: str) -> Dict[str, str]:
    """Build language-specific regex patterns."""
    
    if lang == "cpp":
        # C++ keywords
        keywords = (
            "alignas|alignof|and|and_eq|asm|auto|bitand|bitor|bool|break|case|catch|char|char8_t|char16_t|char32_t|"
            "class|compl|concept|const|consteval|constexpr|constinit|const_cast|continue|co_await|co_return|"
            "co_yield|decltype|default|delete|do|double|dynamic_cast|else|enum|explicit|export|extern|false|"
            "float|for|friend|goto|if|inline|int|long|mutable|namespace|new|noexcept|not|not_eq|nullptr|"
            "operator|or|or_eq|private|protected|public|register|reinterpret_cast|requires|return|short|"
            "signed|sizeof|static|static_assert|static_cast|struct|switch|template|this|thread_local|"
            "throw|true|try|typedef|typeid|typename|union|unsigned|using|virtual|void|volatile|wchar_t|"
            "while|xor|xor_eq|override|final|transaction_safe|transaction_safe_dynamic|nullptr_t"
        )
        types = (
            "string|vector|map|set|unordered_map|unordered_set|list|array|tuple|pair|unique_ptr|shared_ptr|"
            "weak_ptr|optional|variant|any|span|array|deque|forward_list|priority_queue|queue|stack|"
            "multiset|multimap|unordered_multimap|unordered_multiset|bitset|chrono|duration|time_point|"
            "filesystem|path|error_code|error_condition|exception|terminate|unexpected"
        )
        # Match /**/ and // comments, preprocessor, strings, numbers, functions, types
        patterns = [
            (r'//.*', 'comment'),
            (r'/\*[\s\S]*?\*/', 'comment'),
            (r'#\s*\w+', 'preproc'),          # preprocessor
            (r'#\s*include\s*[<"].*[">]', 'preproc'),  # includes
            (r'"""[\s\S]*?"""|"(?:[^"\\]|\\.)*"', 'string'),
            (r"'''[\s\S]*?'''|'(?:[^'\\]|\\.)*'", 'string'),
            (r'\b\d+\.?\d*[fFlL]?\b', 'number'),
            (r'\b0x[0-9a-fA-F]+\b', 'number'),
            (r'\b0b[01]+\b', 'number'),
            (rf'\b({types})\b', 'type'),
            (rf'\b({keywords})\b', 'keyword'),
            (r'\b\w+(?=\s*\()', 'function'),  # word before (
            (r'=>|::|\+\+|--|->|<<|>>|&&|\|\||==|!=|<=|>=|[+\-*/%&|^~<>=]', 'operator'),
        ]
        
    elif lang == "c":
        keywords = (
            "auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|"
            "inline|int|long|register|restrict|return|short|signed|sizeof|static|struct|switch|typedef|"
            "union|unsigned|void|volatile|while|_Alignas|_Alignof|_Atomic|_Bool|_Complex|_Generic|"
            "_Imaginary|_Noreturn|_Static_assert|_Thread_local|asm|typeof|__builtin|__attribute__"
        )
        types = (
            "size_t|ssize_t|int8_t|int16_t|int32_t|int64_t|uint8_t|uint16_t|uint32_t|uint64_t|"
            "intptr_t|uintptr_t|ptrdiff_t|intmax_t|uintmax_t|FILE|DIR|struct|union|enum|..."
        )
        patterns = [
            (r'//.*', 'comment'),
            (r'/\*[\s\S]*?\*/', 'comment'),
            (r'#\s*\w+', 'preproc'),
            (r'#\s*include\s*[<"].*[">]', 'preproc'),
            (r'"""[\s\S]*?"""|"(?:[^"\\]|\\.)*"', 'string'),
            (r"'''[\s\S]*?'''|'(?:[^'\\]|\\.)*'", 'string'),
            (r'\b\d+\.?\d*[fFlL]?\b', 'number'),
            (r'\b0x[0-9a-fA-F]+[uUlL]*\b', 'number'),
            (r'\b0b[01]+[uUlL]*\b', 'number'),
            (rf'\b({types})\b', 'type'),
            (rf'\b({keywords})\b', 'keyword'),
            (r'\b\w+(?=\s*\()', 'function'),
            (r'=>|::|\+\+|--|->|<<|>>|&&|\|\||==|!=|<=|>=|[+\-*/%&|^~<>=]', 'operator'),
        ]
        
    elif lang == "go":
        keywords = (
            "break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|"
            "interface|map|package|range|return|select|struct|switch|type|var|bool|byte|complex64|"
            "complex128|error|float32|float64|int|int8|int16|int32|int64|rune|string|uint|uint8|uint16|"
            "uint32|uint64|uintptr|true|false|nil|iota|append|cap|close|complex|copy|delete|imag|len|make|"
            "new|panic|print|println|real|recover|len|close"
        )
        types = (
            "bool|byte|complex64|complex128|error|float32|float64|int|int8|int16|int32|int64|rune|"
            "string|uint|uint8|uint16|uint32|uint64|uintptr|any|comparable|bool|byte|error|rune|uintptr"
        )
        patterns = [
            (r'//.*', 'comment'),
            (r'/\*[\s\S]*?\*/', 'comment'),
            (r'"(?:[^"\\]|\\.)*"', 'string'),
            (r'`[^`]*`', 'string'),
            (r"'(?:[^'\\]|\\.)'", 'string'),
            (r'\b\d+\.?\d*[eE]?[+-]?\d*f?\b', 'number'),
            (r'\b0x[0-9a-fA-F]+\b', 'number'),
            (r'\b0b[01]+\b', 'number'),
            (rf'\b({keywords})\b', 'keyword'),
            (rf'\b({types})\b', 'type'),
            (r'\b\w+(?=\s*\()', 'function'),
            (r'=>|:=|<-|<<|>>|&&|\|\||==|!=|<=|>=|[+\-*/%&|^<>=]', 'operator'),
        ]
        
    elif lang == "shell":
        keywords = (
            "if|then|else|elif|fi|case|esac|for|while|until|do|done|in|function|select|time|"
            "coproc|exit|return|break|continue|declare|local|readonly|export|unset|shift|getopts|"
            "set|source|alias|unalias|eval|exec|trap|wait|true|false"
        )
        builtins = (
            "echo|printf|read|cd|pwd|ls|mkdir|rmdir|rm|cp|mv|cat|grep|sed|awk|find|xargs|sort|uniq|wc|"
            "head|tail|cut|tr|tee|test|[|let|expr|basename|dirname|realpath|stat|file|which|whereis|"
            "type|command|builtin|compgen|complete|history|jobs|fg|bg|kill|send|wait"
        )
        patterns = [
            (r'#.*', 'comment'),
            (r'"(?:[^"\\]|\\.)*"', 'string'),
            (r"'(?:[^'\\]|\\.)*'", 'string'),
            (r'\$\{?\w+\}?', 'variable'),  # variables
            (r'\$\([^)]+\)', 'command'),    # command substitution
            (r'`[^`]+`', 'command'),       # backtick substitution
            (r'\b\d+\b', 'number'),
            (rf'\b({keywords})\b', 'keyword'),
            (rf'\b({builtins})\b', 'builtin'),
            (r'[|&;(){}<>!~=$]+', 'operator'),
        ]
    else:
        patterns = []
    
    return patterns


def _highlight(code: str, lang: str) -> str:
    """Apply syntax highlighting to code."""
    patterns = _build_patterns(lang)
    if not patterns:
        return code
    
    # Create pattern with named groups to avoid overlapping matches
    # We'll process in order of specificity
    lines = code.split('\n')
    result_lines = []
    
    for line in lines:
        if not line.strip():
            result_lines.append(line)
            continue
        
        # Track positions that are already highlighted
        highlighted = ""
        pos = 0
        line_len = len(line)
        
        # We'll do a simpler approach: find all matches and highlight them
        segments = []
        for pattern, style in patterns:
            for match in re.finditer(pattern, line):
                segments.append((match.start(), match.end(), style, match.group()))
        
        # Sort by start position, then by priority (longer matches first for same position)
        segments.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        
        # Merge overlapping segments
        merged = []
        for start, end, style, text in segments:
            if merged and start <= merged[-1][1]:
                # Overlapping - take the longer match
                if end > merged[-1][1]:
                    merged[-1] = (merged[-1][0], end, style, line[merged[-1][0]:end])
            else:
                merged.append((start, end, style, text))
        
        # Build highlighted line
        out = ""
        last_end = 0
        for start, end, style, text in merged:
            if start < last_end:
                continue
            out += line[last_end:start]
            if style == 'keyword':
                out += f"{C.KEYWORD}{text}{C.RESET}"
            elif style == 'type':
                out += f"{C.TYPE}{text}{C.RESET}"
            elif style == 'string':
                out += f"{C.STRING}{text}{C.RESET}"
            elif style == 'comment':
                out += f"{C.COMMENT}{text}{C.RESET}"
            elif style == 'number':
                out += f"{C.NUMBER}{text}{C.RESET}"
            elif style == 'function':
                out += f"{C.FUNCTION}{text}{C.RESET}"
            elif style == 'preproc':
                out += f"{C.PREPROC}{text}{C.RESET}"
            elif style == 'operator':
                out += f"{C.OPERATOR}{text}{C.RESET}"
            elif style == 'builtin':
                out += f"{C.BUILTIN}{text}{C.RESET}"
            elif style == 'variable':
                out += f"{C.NUMBER}{text}{C.RESET}"
            elif style == 'command':
                out += f"{C.STRING}{text}{C.RESET}"
            else:
                out += text
            last_end = end
        
        out += line[last_end:]
        result_lines.append(out)
    
    return '\n'.join(result_lines)


def highlight_cpp(code: str) -> str:
    """Highlight C++ code."""
    return _highlight(code, "cpp")


def highlight_c(code: str) -> str:
    """Highlight C code."""
    return _highlight(code, "c")


def highlight_go(code: str) -> str:
    """Highlight Go code."""
    return _highlight(code, "go")


def highlight_shell(code: str) -> str:
    """Highlight Shell/Bash code."""
    return _highlight(code, "shell")


def detect_and_highlight(code: str) -> str:
    """Auto-detect language and highlight."""
    # Simple heuristics
    lines = code.split('\n')
    if not lines:
        return code
    
    # Check for common patterns
    if re.search(r'\bpackage\s+\w+', code) and re.search(r'\bfunc\s+\w+', code):
        return highlight_go(code)
    if re.search(r'#include\s*<', code) and re.search(r'\b(std::|cout|cin)\b', code):
        return highlight_cpp(code)
    if re.search(r'#include\s*<', code) and re.search(r'\b(printf|scanf|malloc)\b', code):
        return highlight_c(code)
    if re.search(r'^#!.*/(ba)?sh', code, re.MULTILINE) or re.search(r'\becho\b', code):
        return highlight_shell(code)
    if re.search(r'\bclass\s+\w+.*\{', code):
        return highlight_cpp(code)
    if re.search(r'\bfunc\s', code):
        return highlight_go(code)
    if re.search(r'\bvoid\s+\w+\(.*\)\s*\{', code):
        return highlight_c(code)
    if re.search(r'^(\w+\(\)|while|for|if|else)\b', code, re.MULTILINE):
        return highlight_shell(code)
    
    # Default
    return code


# ─── Pretty Print for Display ─────────────────────────────────────────────────

def print_code(code: str, lang: Optional[str] = None, line_numbers: bool = True) -> None:
    """Print code with syntax highlighting.
    
    Args:
        code: Source code to print
        lang: Language hint ('cpp', 'c', 'go', 'shell') or None for auto-detect
        line_numbers: Show line numbers
    """
    if lang is None:
        lang = "cpp"  # default
        if '#include' in code and ('std::' in code or 'cout' in code):
            lang = "cpp"
        elif 'package ' in code and 'func ' in code:
            lang = "go"
        elif '#include' in code:
            lang = "c"
        elif '#!/' in code or 'echo ' in code or 'export ' in code.split('\n')[0]:
            lang = "shell"
    
    highlighted = _highlight(code, lang)
    lines = highlighted.split('\n')
    
    width = max(len(str(len(lines))), 2)
    for i, line in enumerate(lines, 1):
        if line_numbers:
            num = str(i).rjust(width)
            print(f"{C.DIM}{num}|{C.RESET} {line}")
        else:
            print(line)


if __name__ == "__main__":
    # Test
    cpp_code = '''
#include <iostream>
#include <vector>
#include <string>

int main() {
    std::vector<std::string> names = {"Alice", "Bob"};
    for (const auto& name : names) {
        std::cout << "Hello, " << name << "!" << std::endl;
    }
    return 0;
}
'''
    print("=== C++ ===")
    print_code(cpp_code, "cpp")
    
    c_code = '''
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char* argv[]) {
    int* data = malloc(100 * sizeof(int));
    for (int i = 0; i < 100; i++) {
        data[i] = i * 2;
    }
    free(data);
    return 0;
}
'''
    print("\n=== C ===")
    print_code(c_code, "c")
    
    go_code = '''
package main

import "fmt"

func main() {
    names := []string{"Alice", "Bob"}
    for _, name := range names {
        fmt.Printf("Hello, %s!\\n", name)
    }
}
'''
    print("\n=== Go ===")
    print_code(go_code, "go")
    
    shell_code = '''
#!/bin/bash
export PATH=/usr/local/bin:$PATH

for item in *.txt; do
    echo "Processing: $item"
done
'''
    print("\n=== Shell ===")
    print_code(shell_code, "shell")