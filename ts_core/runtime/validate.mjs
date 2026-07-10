/**
 * MINXG TypeScript Schema Validator — pure-JS runtime version
 * Mirrors src/validate.ts so Node can run it without a TS compilation step.
 */

const VALID_ROLES = new Set(["system", "user", "assistant", "tool"]);

function validateMessage(raw) {
    if (typeof raw !== "object" || raw === null) return null;
    const m = raw;
    const role = m.role;
    if (typeof role !== "string" || !VALID_ROLES.has(role)) return null;
    const content = m.content;
    if (content !== null && typeof content !== "string") return null;
    const out = { role, content };
    if (typeof m.name === "string") out.name = m.name;
    if (Array.isArray(m.tool_calls)) out.tool_calls = m.tool_calls;
    if (typeof m.tool_call_id === "string") out.tool_call_id = m.tool_call_id;
    return out;
}

function validateMessages(raw) {
    if (!Array.isArray(raw)) return null;
    const out = [];
    for (const item of raw) {
        const v = validateMessage(item);
        if (!v) return null;
        out.push(v);
    }
    return out.length ? out : null;
}

function validateChatRequest(raw) {
    if (typeof raw !== "object" || raw === null) {
        return { ok: false, error: "Request must be an object" };
    }
    const r = raw;
    if (typeof r.model !== "string" || r.model.length === 0) {
        return { ok: false, error: "Missing 'model' field" };
    }
    const msgs = validateMessages(r.messages);
    if (!msgs) {
        return { ok: false, error: "'messages' must be a non-empty array of valid messages" };
    }
    return { ok: true, value: { model: r.model, messages: msgs } };
}

export { validateMessage, validateMessages, validateChatRequest };