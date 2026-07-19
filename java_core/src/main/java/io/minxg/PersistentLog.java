package io.minxg;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Persistent structured log — append-only with bounded retention.
 *
 * Used for in-process telemetry: tool calls, latencies, errors. The
 * daemon is in-memory; persistence to disk is the worker's
 * responsibility. Query supports substring token overlap with a
 * per-field tag filter.
 */
public final class PersistentLog {

    private static final class Entry {
        final long ts;
        final String level;
        final String tag;
        final String message;

        Entry(long ts, String level, String tag, String message) {
            this.ts = ts;
            this.level = level;
            this.tag = tag;
            this.message = message;
        }
    }

    private final ConcurrentHashMap<Long, Entry> ring =
            new ConcurrentHashMap<>();
    private final List<Entry> order = new ArrayList<>();
    private final Object orderLock = new Object();
    private static final int MAX_ENTRIES = 4096;

    public Json append(Json req) {
        String level = req.str("level");
        if (level == null) {
            level = "INFO";
        }
        String tag = req.str("tag");
        if (tag == null) {
            tag = "general";
        }
        String message = req.str("message");
        if (message == null) {
            return Json.object().put("ok", false)
                    .put("error", "missing message");
        }
        long ts = req.integer("ts");
        if (ts == 0) {
            ts = System.currentTimeMillis();
        }
        Entry e = new Entry(ts, level, tag, message);
        synchronized (orderLock) {
            order.add(e);
            while (order.size() > MAX_ENTRIES) {
                Entry dropped = order.remove(0);
                ring.remove(dropped.ts);
            }
            ring.put(ts, e);
        }
        return Json.object().put("ok", true)
                .put("ts", ts)
                .put("total", ring.size());
    }

    public Json query(Json req) {
        String q = req.str("q");
        String tag = req.str("tag");
        int k = Math.max(1, req.integer("k"));
        List<Entry> entries;
        synchronized (orderLock) {
            entries = new ArrayList<>(order);
        }
        // newest-first
        java.util.Collections.reverse(entries);
        Set<String> qTokens = tokens(q);
        Json out = Json.object().put("ok", true)
                .put("count", entries.size())
                .put("matched", 0);
        Json hits = Json.array();
        int matched = 0;
        for (Entry e : entries) {
            if (tag != null && !tag.equals(e.tag)) {
                continue;
            }
            if (!qTokens.isEmpty()) {
                Set<String> msgTokens = tokens(e.message);
                boolean ok = false;
                for (String t : qTokens) {
                    if (msgTokens.contains(t)) {
                        ok = true;
                        break;
                    }
                }
                if (!ok) {
                    continue;
                }
            }
            Json h = Json.object()
                    .put("ts", e.ts)
                    .put("level", e.level)
                    .put("tag", e.tag)
                    .put("message", preview(e.message));
            hits.add(h);
            matched++;
            if (matched >= k) {
                break;
            }
        }
        out.put("matched", matched).put("hits", hits);
        return out;
    }

    public int entryCount() {
        return ring.size();
    }

    private static Set<String> tokens(String s) {
        Set<String> out = new HashSet<>();
        if (s == null) {
            return out;
        }
        int n = s.length();
        int i = 0;
        while (i < n) {
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
                }
            }
        }
        return out;
    }

    private static boolean isWord(char c) {
        return Character.isLetterOrDigit(c) || c == '_';
    }

    private static String preview(String s) {
        if (s.length() <= 256) {
            return s;
        }
        return s.substring(0, 253) + "...";
    }
}
