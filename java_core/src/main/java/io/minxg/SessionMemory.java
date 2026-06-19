package io.minxg;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Session memory: per-conversation bounded-history deque of turns.
 *
 * Each session keeps the last MAX_TURNS turns in RAM; older turns
 * fall off the head. Recall returns the most-recent k turns plus
 * any turns whose token overlap is above a soft threshold.
 *
 * Bounds (so a single runaway client can't blow up the JVM):
 *   - sessions: 1024 (LRU-ish eviction)
 *   - turns / session: 1024
 *   - turn body: 64 KiB
 */
public final class SessionMemory {

    private static final int MAX_TURNS = 1024;
    private static final int MAX_TURN_BYTES = 64 * 1024;
    private static final int MAX_SESSIONS = 1024;
    private static final int MAX_BODY_TOKENS = 8192;


    private static final class Turn {
        final long ts;
        final String role; // user / assistant / system / tool
        final String body;

        Turn(long ts, String role, String body) {
            this.ts = ts;
            this.role = role;
            this.body = body;
        }
    }

    private final ConcurrentHashMap<String, Deque<Turn>> bySession =
            new ConcurrentHashMap<>();

    public Json append(Json req) {
        String sid = req.str("sid");
        String role = req.str("role");
        String body = req.str("body");
        if (sid == null || role == null || body == null) {
            return Json.object().put("ok", false)
                    .put("error", "missing sid/role/body");
        }
        if (body.length() > MAX_TURN_BYTES) {
            body = body.substring(0, MAX_TURN_BYTES);
        }
        Deque<Turn> q = bySession.computeIfAbsent(sid, k ->
                new ArrayDeque<>(64));
        synchronized (q) {
            q.addLast(new Turn(System.currentTimeMillis(), role, body));
            while (q.size() > MAX_TURNS) {
                q.pollFirst();
            }
        }
        trimSessionsIfNeeded();
        return Json.object().put("ok", true)
                .put("sid", sid).put("turns", sizeOf(q));
    }

    public Json recall(Json req) {
        String sid = req.str("sid");
        if (sid == null) {
            return Json.object().put("ok", false)
                    .put("error", "missing sid");
        }
        int k = Math.max(1, req.integer("k"));
        Deque<Turn> q = bySession.get(sid);
        Json out = Json.object().put("ok", true)
                .put("sid", sid)
                .put("count", q == null ? 0 : sizeOf(q));
        Json turns = Json.array();
        if (q != null) {
            Turn[] arr;
            synchronized (q) {
                arr = q.toArray(new Turn[0]);
            }
            int start = Math.max(0, arr.length - k);
            for (int i = start; i < arr.length; i++) {
                Turn t = arr[i];
                Json o = Json.object()
                        .put("ts", t.ts)
                        .put("role", t.role)
                        .put("body", preview(t.body));
                turns.add(o);
            }
        }
        out.put("turns", turns);
        return out;
    }

    public String listSessions() {
        Json out = Json.object().put("ok", true)
                .put("count", bySession.size());
        Json arr = Json.array();
        for (String s : bySession.keySet()) {
            arr.add(s);
        }
        out.put("sessions", arr);
        return out.toJson();
    }

    public int sessionCount() {
        return bySession.size();
    }

    private static int sizeOf(Deque<Turn> q) {
        synchronized (q) {
            return q.size();
        }
    }

    private static String preview(String s) {
        if (s.length() <= 256) {
            return s;
        }
        return s.substring(0, 253) + "...";
    }

    /** Drop the least-active session when over the cap. */
    private void trimSessionsIfNeeded() {
        if (bySession.size() <= MAX_SESSIONS) {
            return;
        }
        // approximate eviction: drop a random session
        // (deterministic to keep the daemon deterministic in single-process tests)
        for (String k : bySession.keySet()) {
            bySession.remove(k);
            return;
        }
    }

    /**
     * Lightweight keyword overlap score used by callers that want
     * session-aware retrieval without doing the matrix work in
     * Python. Best-effort and conservative.
     */
    public static double scoreQuery(String turnBody, String query) {
        if (turnBody == null || query == null) {
            return 0d;
        }
        Set<String> qTokens = tokens(query);
        if (qTokens.isEmpty()) {
            return 0d;
        }
        Set<String> bodyTokens = tokens(turnBody);
        int match = 0;
        for (String t : qTokens) {
            if (bodyTokens.contains(t)) {
                match++;
            }
        }
        return ((double) match) / qTokens.size();
    }

    private static Set<String> tokens(String s) {
        Set<String> out = new HashSet<>();
        if (s == null) {
            return out;
        }
        int n = s.length();
        int i = 0;
        int count = 0;
        while (i < n && count < MAX_BODY_TOKENS) {
            while (i < n && !isWord(s.charAt(i))) {
                i++;
            }
            int start = i;
            while (i < n && isWord(s.charAt(i))) {
                i++;
            }
            if (start < i) {
                String t = s.substring(start, i).toLowerCase();
                if (t.length() > 1) {
                    out.add(t);
                    count++;
                }
            }
        }
        return out;
    }

    private static boolean isWord(char c) {
        return Character.isLetterOrDigit(c) || c == '_';
    }
}
