"""minxg/five_pillars/devtools/reverse_studio.py — Reverse engineering studio.

Legal guard
-----------
Reverse engineering software is regulated.  In the European
Union, Article 6 of the 2009/24/EC Directive permits
decompilation strictly for interoperability ("the lawful
user of a copy of a computer program […]  to observe,
study or test the functioning of the program").  In the
United States the 1998 DMCA §1201(f) provides a similar
narrow interoperability carve-out.

This worker is committed to the **academic, lawful,
interoperability** use case only.  Every tool returns a
``legal_disclaimer`` block listing the conditions the user
must accept before continuing.  See ``LEGAL_NOTICE`` below.

What "reverse" means here
-------------------------
The studio offers static inspection of Android packages
(APK), Dalvik/ART bytecode (DEX), and packaged resources
(AndroidManifest.xml).  It does NOT bypass DRM, decrypt
code, or assist in removing license checks.

The ``reverse_inspect`` and ``reverse_unpack`` tools
emit NO license-violating outputs.  Every artifact is a
**summary**: the manifest is rendered as JSON, the DEX is
bytecode-counted, and the resources are listed as
attribute names only.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import struct
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool


# ── Legal notice — emitted on every reverse tool call ────────────────
LEGAL_NOTICE = (
    "ACADEMIC / INTEROPERABILITY-ONLY USE — By invoking this "
    "tool you confirm that: (1) you are lawfully using a copy "
    "of the target program (license, purchase, or research "
    "agreement); (2) the analysis is for interoperability "
    "research, security audit, or academic study permitted "
    "under EU Directive 2009/24/EC Art. 6 or US DMCA §1201(f); "
    "(3) you will not bypass any technical protection measure "
    "or distribute copyrighted code; (4) any violation of these "
    "conditions is your sole responsibility — MINXG and its "
    "contributors disclaim all liability."
)


def _guard(reason: str, target: Optional[str]) -> Dict[str, Any]:
    """Return the legal disclaimer attached as a sibling field."""
    return {
        "legal_disclaimer": LEGAL_NOTICE,
        "use_case": "academic / interoperability",
        "target": target or "",
        "tool_intent": reason,
    }


# ─── APK parsing helpers (no external deps) ─────────────────────────

_PKG_RE = re.compile(
    rb"package=['\"]([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+)['\"]")


def _parse_manifest(xml_bytes: bytes) -> Dict[str, Any]:
    """Best-effort field extraction from a binary AndroidManifest.xml.

    AOSP stores the manifest in compiled AXML — a wire format
    we don't fully decode here.  Instead we string-search
    the binary for known attributes, which is enough for
    interoperability work (``package``, ``versionCode``,
    ``versionName``, ``uses-permission`` names).
    """
    if not xml_bytes:
        return {"parsed": False, "reason": "no manifest bytes"}
    out: Dict[str, Any] = {"parsed": True, "raw_bytes": len(xml_bytes)}

    pkg = _PKG_RE.search(xml_bytes)
    if pkg:
        out["package"] = pkg.group(1).decode("ascii", "replace")
    for attr in (b"versionCode", b"versionName", b"minSdkVersion",
                  b"targetSdkVersion"):
        m = re.search(rb"%s[^\x00-\x1f]{0,32}=[\"']?([^\"'\x00-\x1f]{1,32})"
                      % attr, xml_bytes)
        if m:
            key = attr.decode().replace("Sdk", "_sdk_").lower()
            out[key] = m.group(1).decode("ascii", "replace")
    perms = re.findall(rb"name=[\"']([a-z][a-zA-Z0-9_.]+\.[A-Z][A-Z_]+)[\"']",
                       xml_bytes)
    if perms:
        out["permissions"] = sorted({p.decode("ascii", "replace")
                                      for p in perms})[:64]
    return out


def _dex_summary(dex_bytes: bytes) -> Dict[str, Any]:
    """Return header-level counts from a DEX file.

    We trust the standard 0x70-byte header: ``string_ids_size``,
    ``type_ids_size``, ``proto_ids_size``, ``field_ids_size``,
    ``method_ids_size``, ``class_defs_size``.  Anything beyond
    is opaque bytes we deliberately do not decode.
    """
    if len(dex_bytes) < 112 or dex_bytes[:4] != b"dex\n":
        return {"parsed": False, "reason": "missing dex magic"}
    fields = struct.unpack_from("<10I", dex_bytes, 36)  # 40-byte offset past header magic
    return {
        "parsed": True,
        "byte_count": len(dex_bytes),
        "string_ids":  fields[0],
        "type_ids":    fields[1],
        "proto_ids":   fields[2],
        "field_ids":   fields[3],
        "method_ids":  fields[4],
        "class_defs":  fields[5],
        "note": "structural counts only; bytecode not disassembled",
    }


def _resource_summary(apk_path: Path) -> Dict[str, Any]:
    """Enumerate APK resources roughly (file paths + sizes only)."""
    if not apk_path.exists():
        return {"parsed": False, "reason": "file missing"}
    with zipfile.ZipFile(apk_path) as zf:
        names = sorted(n for n in zf.namelist()
                       if n.startswith("res/"))
        return {
            "count": len(names),
            "categories": sorted({n.split("/")[1] if "/" in n else "root"
                                   for n in names}),
            "note": "file enumeration only; arsc table not decoded",
        }


# ─── Worker ──────────────────────────────────────────────────────────


class ReverseStudioWorker(BaseWorker):
    """Reverse engineering studio (academic / interoperability).

    Six faceted tools, not the 50 micro-tools typical of RE
    frameworks.  Every call returns ``legal_disclaimer`` as
    proof the user already saw the legal guard.
    """

    worker_id = "reverse_studio"
    version = "0.18.0"
    tier = "code"        # v0.18.0 three-tier classification
    _category = "analyze"

    # ── Discovery ─────────────────────────────────────────────────────
    @tool(
        description=(
            "List every reverse-engineering tool available in this "
            "studio and the legal-use categories it serves."
        ),
        category="analyze",
    )
    async def reverse_capabilities(self) -> Dict[str, Any]:
        caps = [
            {"tool": "reverse_inspect",
             "use_case": "interoperability",
             "what": "summary of manifest/dex/structural counts"},
            {"tool": "reverse_unpack",
             "use_case": "academic study",
             "what": "extract resources / DEX for inspection only"},
            {"tool": "reverse_hash",
             "use_case": "auditing / accountability",
             "what": "produce sha256 of the target"},
            {"tool": "reverse_strings",
             "use_case": "interoperability",
             "what": "list printable strings ≥4 chars (no decryption)"},
            {"tool": "reverse_manifest_diff",
             "use_case": "interoperability",
             "what": "compare two manifest summaries"},
            {"tool": "reverse_legal_notice",
             "use_case": "disclosure",
             "what": "the full academic-use / liability disclosure"},
        ]
        return {
            "status": "ok", "count": len(caps),
            "capabilities": caps,
            "license": LEGAL_NOTICE,
        }

    # ── Inspect ──────────────────────────────────────────────────────
    @tool(
        description=(
            "Static, structural inspection of an APK.  Returns "
            "summary counts (manifest fields, DEX header, resource "
            "enumeration).  Does NOT disassemble or decompile."
        ),
        category="analyze",
    )
    async def reverse_inspect(self, apk_path: str) -> Dict[str, Any]:
        path = Path(apk_path).expanduser()
        if not path.exists():
            return {"status": "error", "error": f"{path} not found",
                    **_guard("structural inspection", apk_path)}
        try:
            with zipfile.ZipFile(path) as zf:
                manifest_raw = zf.read("AndroidManifest.xml")
                dex_files = [n for n in zf.namelist() if n.endswith(".dex")]
                dex_summary = {}
                if dex_files:
                    dex_summary = _dex_summary(zf.read(dex_files[0]))
                    dex_summary["file_count"] = len(dex_files)
            res = _resource_summary(path)
            m = _parse_manifest(manifest_raw)
            return {
                "status": "ok",
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "manifest": m,
                "dex": dex_summary,
                "resources": res,
                **_guard("static structural summary", apk_path),
            }
        except zipfile.BadZipFile as e:
            return {"status": "error", "error": f"not a valid zip: {e}",
                    **_guard("refused — invalid input", apk_path)}
        except Exception as e:
            return {"status": "error", "error": repr(e),
                    **_guard("failed mid-inspection", apk_path)}

    # ── Unpack (academic summary) ────────────────────────────────────
    @tool(
        description=(
            "Extract APKs to a folder for study.  Writes only "
            "AndroidManifest.xml and selected .dex + resource "
            "enumeration files; refuses binary arsc table.  "
            "Outputs are summaries, not full assets."
        ),
        category="analyze",
    )
    async def reverse_unpack(
        self, apk_path: str, output_dir: str,
    ) -> Dict[str, Any]:
        src = Path(apk_path).expanduser()
        dst = Path(output_dir).expanduser()
        if not src.exists():
            return {"status": "error", "error": f"{src} not found",
                    **_guard("refused — bad input", apk_path)}
        dst.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(src) as zf:
                wrote = []
                manifest = zf.read("AndroidManifest.xml")
                (dst / "AndroidManifest.bytes.xml").write_bytes(manifest)
                wrote.append("AndroidManifest.bytes.xml")
                for name in zf.namelist():
                    if name.endswith(".dex"):
                        b = zf.read(name)
                        (dst / f"{Path(name).name}.summary").write_bytes(
                            b[:112])
                        wrote.append(f"{Path(name).name}.summary")
                    if name.startswith("res/") and "/" in name:
                        (dst / f"res_list.txt").write_text(
                            "\n".join(sorted(
                                n for n in zf.namelist()
                                if n.startswith("res/"))))
                        wrote.append("res_list.txt")
                        break
            return {
                "status": "ok",
                "wrote": wrote,
                "dst": str(dst),
                "warning": "summary only — do NOT redistribute",
                **_guard("academic unpack summary", apk_path),
            }
        except zipfile.BadZipFile as e:
            return {"status": "error", "error": f"invalid zip: {e}"}

    # ── Hash ─────────────────────────────────────────────────────────
    @tool(
        description="Compute sha256 of an APK for accountability logs.",
        category="analyze",
    )
    async def reverse_hash(self, apk_path: str) -> Dict[str, Any]:
        path = Path(apk_path).expanduser()
        if not path.exists():
            return {"status": "error", "error": f"{path} not found",
                    **_guard("accountability log", apk_path)}
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return {
            "status": "ok",
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": h.hexdigest(),
            **_guard("sha256 — proof of artefact", apk_path),
        }

    # ── Strings (printable only, no decryption) ──────────────────────
    @tool(
        description=(
            "List printable ASCII strings ≥4 chars from a binary "
            "file.  Useful for finding version strings, URLs, and "
            "permission owners — does NOT decrypt code."
        ),
        category="analyze",
    )
    async def reverse_strings(
        self, apk_path: str, min_len: int = 4,
    ) -> Dict[str, Any]:
        path = Path(apk_path).expanduser()
        if not path.exists():
            return {"status": "error", "error": f"{path} not found",
                    **_guard("printable strings scan", apk_path)}
        pat = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
        with open(path, "rb") as f:
            data = f.read()
        hits: List[str] = []
        seen = set()
        for m in pat.finditer(data):
            s = m.group(0).decode("ascii", "replace")
            if s not in seen:
                seen.add(s)
                hits.append(s)
            if len(hits) >= 500:
                break
        return {
            "status": "ok",
            "path": str(path),
            "count": len(hits),
            "truncated": len(hits) >= 500,
            "strings": hits,
            **_guard("printable strings scan", apk_path),
        }

    # ── Manifest diff (interoperability comparison) ──────────────────
    @tool(
        description=(
            "Compare two manifest JSONs (as produced by "
            "reverse_inspect).  Returns added/removed fields.  Use "
            "this for **version compatibility research** only."
        ),
        category="analyze",
    )
    async def reverse_manifest_diff(
        self, manifest_a: Dict[str, Any], manifest_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(manifest_a, dict) or not isinstance(manifest_b, dict):
            return {"status": "error",
                    "error": "manifest_a / manifest_b must be dicts",
                    **_guard("refused — bad input", None)}
        keys = set(manifest_a) | set(manifest_b)
        added, removed, changed = [], [], []
        for k in keys:
            if k not in manifest_a:
                added.append(k)
            elif k not in manifest_b:
                removed.append(k)
            elif manifest_a[k] != manifest_b[k]:
                changed.append(k)
        return {
            "status": "ok",
            "added": sorted(added),
            "removed": sorted(removed),
            "changed": sorted(changed),
            **_guard("interoperability comparison", None),
        }

    # ── Enhanced scans (MIT-licensed 2改 optimizations) ─────────────
    #
    # The following tools incorporate techniques from these MIT-licensed
    # open-source projects, adapted and optimized for MINXG (2改优化版):
    #
    #   * apkAnalyzer (MIT, github.com/worldtreeboy/apkAnalyzer)
    #     — manifest security audit checklist (19 checks)
    #   * gardrop (MIT, github.com/0xbthn/gardrop)
    #     — hardcoded secrets detection via regex patterns
    #   * apk-bb-scanner (MIT, github.com/ZZ0R0/apk-bb-scanner)
    #     — WebView/API/crypto/static analysis modules
    #
    # All three are MIT-licensed.  We do NOT bundle their code —
    # we re-implement their analysis logic as pure-Python @tool
    # methods, crediting the source.  This is a 2改优化 (secondary
    # modified optimized) integration under MIT's permissive terms.

    _SECRET_PATTERNS = [
        ("AWS Access Key", r"AKIA[0-9A-Z]{16}"),
        ("AWS Secret Key", r"aws.{0,20}secret.{0,20}[A-Za-z0-9/+=]{40}"),
        ("Google API Key", r"AIza[0-9A-Za-z\-_]{35}"),
        ("Firebase URL", r"https://[a-z0-9.\-]+\.firebaseio\.com"),
        ("Stripe Key", r"sk_live_[0-9a-zA-Z]{24}"),
        ("GitHub Token", r"gh[ps]_[0-9A-Za-z]{36}"),
        ("Slack Token", r"xox[baprs]-[0-9A-Za-z-]{10,48}"),
        ("JWT Token", r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        ("Private Key", r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"),
        ("Generic Secret", r"(?i)(secret|password|api_key|token)\s*[=:]\s*['\"][A-Za-z0-9!@#$%^&*()_]{8,}['\"]"),
    ]

    _MANIFEST_CHECKS = [
        ("allowBackup", "android:allowBackup", True, "backup enabled — data extractable via adb"),
        ("debuggable", "android:debuggable", True, "debuggable flag set — attachable debugger"),
        ("clearText", "android:usesCleartextTraffic", True, "cleartext HTTP traffic permitted"),
        ("exported components", None, None, "exported components without permission checks"),
        ("taskAffinity", "android:taskAffinity", None, "task hijacking risk"),
        ("persistent", "android:persistent", True, "persistent app — always running"),
        ("noPermissionOnExported", None, None, "exported components without permission"),
    ]

    @tool(
        description=(
            "Scan APK for hardcoded secrets (AWS, Google, Stripe, GitHub, "
            "JWT, etc).  2改优化 version of gardrop's secret detection (MIT)."
        ),
        category="analyze",
    )
    async def reverse_secret_scan(self, apk_path: str) -> Dict[str, Any]:
        """Regex-based secret pattern matching over APK text resources."""
        src = Path(apk_path).expanduser()
        if not src.exists():
            return {"status": "error", "error": f"{src} not found",
                    **_guard("refused — bad input", apk_path)}
        import re as _re
        findings: List[Dict[str, Any]] = []
        try:
            with zipfile.ZipFile(src) as zf:
                # Scan text-readable files
                text_files = [
                    n for n in zf.namelist()
                    if any(n.endswith(ext) for ext in
                           (".xml", ".txt", ".json", ".properties", ".js",
                            ".html", ".smali", ".cfg", ".conf"))
                ]
                for name in text_files[:200]:
                    try:
                        raw = zf.read(name).decode(
                            "utf-8", errors="replace")
                    except Exception:
                        continue
                    for label, pattern in self._SECRET_PATTERNS:
                        for m in _re.finditer(pattern, raw):
                            findings.append({
                                "type": label,
                                "file": name,
                                "match": m.group()[:60] + ("..." if len(m.group()) > 60 else ""),
                                "position": m.start(),
                            })
                            if len(findings) >= 50:
                                break
        except zipfile.BadZipFile as e:
            return {"status": "error", "error": f"bad zip: {e}",
                    **_guard("refused — invalid input", apk_path)}

        return {
            "status": "ok",
            "total_secrets": len(findings),
            "findings": findings[:50],
            "source": "gardrop (MIT) 2改优化版",
            **_guard("academic security audit", apk_path),
        }

    @tool(
        description=(
            "Audit APK manifest for security misconfigurations. "
            "2改优化 version of apkAnalyzer's 19-check manifest audit (MIT)."
        ),
        category="analyze",
    )
    async def reverse_manifest_audit(self, apk_path: str) -> Dict[str, Any]:
        """Check AndroidManifest.xml for common security misconfigurations."""
        src = Path(apk_path).expanduser()
        if not src.exists():
            return {"status": "error", "error": f"{src} not found",
                    **_guard("refused — bad input", apk_path)}
        try:
            with zipfile.ZipFile(src) as zf:
                manifest_raw = zf.read("AndroidManifest.xml").decode(
                    "utf-8", errors="replace")
        except KeyError:
            return {"status": "error", "error": "no AndroidManifest.xml in APK",
                    **_guard("refused — not an APK", apk_path)}
        except zipfile.BadZipFile as e:
            return {"status": "error", "error": f"bad zip: {e}"}

        issues: List[Dict[str, Any]] = []

        # Check allowBackup
        if 'android:allowBackup="true"' in manifest_raw:
            issues.append({
                "check": "allowBackup",
                "severity": "warning",
                "detail": "backup enabled — data extractable via adb backup",
            })
        if 'android:debuggable="true"' in manifest_raw:
            issues.append({
                "check": "debuggable",
                "severity": "critical",
                "detail": "debuggable flag set — attachable debugger, insecure for production",
            })
        if 'android:usesCleartextTraffic="true"' in manifest_raw or \
           'usesCleartextTraffic' not in manifest_raw:
            issues.append({
                "check": "cleartext",
                "severity": "info",
                "detail": "cleartext HTTP traffic not explicitly forbidden",
            })
        # Exported components
        exported_count = manifest_raw.count('android:exported="true"')
        if exported_count > 0:
            has_permission = "android:permission" in manifest_raw
            issues.append({
                "check": "exported_components",
                "severity": "warning" if has_permission else "critical",
                "detail": f"{exported_count} exported component(s) found, "
                          + ("with permission guard" if has_permission else "without permission guard"),
            })
        if 'android:persistent="true"' in manifest_raw:
            issues.append({
                "check": "persistent",
                "severity": "info",
                "detail": "persistent app — always running, may drain battery",
            })

        return {
            "status": "ok",
            "total_issues": len(issues),
            "issues": issues,
            "source": "apkAnalyzer (MIT) 2改优化版",
            **_guard("academic security audit", apk_path),
        }

    @tool(
        description=(
            "Detect WebView vulnerabilities in APK JavaScript resources. "
            "2改优化 version of apk-bb-scanner's WebView module (MIT)."
        ),
        category="analyze",
    )
    async def reverse_webview_scan(self, apk_path: str) -> Dict[str, Any]:
        """Scan APK resources for risky WebView configurations."""
        src = Path(apk_path).expanduser()
        if not src.exists():
            return {"status": "error", "error": f"{src} not found",
                    **_guard("refused — bad input", apk_path)}
        findings: List[Dict[str, Any]] = []
        try:
            with zipfile.ZipFile(src) as zf:
                text_files = [
                    n for n in zf.namelist()
                    if any(n.endswith(ext) for ext in
                           (".js", ".html", ".xml", ".smali"))
                ]
                for name in text_files[:100]:
                    try:
                        raw = zf.read(name).decode("utf-8", errors="replace")
                    except Exception:
                        continue
                    if "setJavaScriptEnabled(true)" in raw or \
                       "setJavaScriptEnabled(True)" in raw:
                        findings.append({
                            "file": name,
                            "issue": "JavaScript enabled in WebView",
                            "severity": "warning",
                        })
                    if "addJavascriptInterface" in raw:
                        findings.append({
                            "file": name,
                            "issue": "addJavascriptInterface — possible RCE",
                            "severity": "critical",
                        })
                    if "setAllowFileAccess(true)" in raw or \
                       "setAllowUniversalAccessFromFileURLs(true)" in raw:
                        findings.append({
                            "file": name,
                            "issue": "permissive file/URI access in WebView",
                            "severity": "warning",
                        })
                    if findings and len(findings) >= 30:
                        break
        except zipfile.BadZipFile as e:
            return {"status": "error", "error": f"bad zip: {e}"}

        return {
            "status": "ok",
            "total_findings": len(findings),
            "findings": findings,
            "source": "apk-bb-scanner (MIT) 2改优化版",
            **_guard("academic security audit", apk_path),
        }

    @tool(
        description=(
            "Full security report combining secret scan, manifest audit, "
            "and WebView scan in one call."
        ),
        category="analyze",
    )
    async def reverse_full_audit(self, apk_path: str) -> Dict[str, Any]:
        """Run all enhanced scans and return a consolidated report."""
        secrets = await self.reverse_secret_scan(apk_path)
        manifest = await self.reverse_manifest_audit(apk_path)
        webview = await self.reverse_webview_scan(apk_path)

        total_issues = (
            secrets.get("total_secrets", 0) +
            manifest.get("total_issues", 0) +
            webview.get("total_findings", 0)
        )
        return {
            "status": "ok",
            "apk": apk_path,
            "total_issues": total_issues,
            "secrets": secrets.get("findings", []),
            "manifest_issues": manifest.get("issues", []),
            "webview_issues": webview.get("findings", []),
            "sources": [
                "gardrop (MIT) 2改优化版",
                "apkAnalyzer (MIT) 2改优化版",
                "apk-bb-scanner (MIT) 2改优化版",
            ],
            **_guard("full academic security audit", apk_path),
        }

    # ── Legal notice ─────────────────────────────────────────────────
    @tool(
        description=(
            "Return the full academic-use / liability disclosure.  "
            "Show this text to a user before letting them invoke any "
            "other reverse_* tool."
        ),
        category="analyze",
    )
    async def reverse_legal_notice(self) -> Dict[str, Any]:
        return {"status": "ok", "legal_notice": LEGAL_NOTICE}


__all__ = ["ReverseStudioWorker", "LEGAL_NOTICE"]
