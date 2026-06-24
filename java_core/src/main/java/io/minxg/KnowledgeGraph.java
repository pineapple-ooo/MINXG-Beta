package io.minxg;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Knowledge graph: documents (id -> content) plus a directed
 * adjacency list for entity links.
 *
 * Query model:
 *   - put: store a document by id, replace if it exists.
 *   - query: substring-match over content (Jaccard on tokens), top-k.
 *   - link: add a directed edge src -> dst.
 *
 * Inspection operations never block writes; the maps are
 * ConcurrentHashMap. Topology lookups use sets behind a
 * per-document lock-free immutable snapshot.
 */
public final class KnowledgeGraph {

    private final ConcurrentHashMap<String, String> docs =
            new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Set<String>> outgoing =
            new ConcurrentHashMap<>();

    public Json put(Json req) {
        String id = req.str("did");
        String content = req.str("content");
        if (id == null || content == null) {
            return Json.object().put("ok", false)
                    .put("error", "missing did/content");
        }
        docs.put(id, content);
        return Json.object().put("ok", true)
                .put("did", id)
                .put("bytes", content.length());
    }

    public Json query(Json req) {
        String q = req.str("q");
        int k = Math.max(1, req.integer("k"));
        if (q == null || q.isEmpty()) {
            return Json.object().put("ok", false)
                    .put("error", "missing q");
        }
        Set<String> qTokens = tokenize(q);
        if (qTokens.isEmpty()) {
            return Json.object().put("ok", true).put("hits", Json.array());
        }
        List<Hit> scored = new ArrayList<>();
        for (java.util.Map.Entry<String, String> e : docs.entrySet()) {
            Set<String> dTokens = tokenize(e.getValue());
            if (dTokens.isEmpty()) {
                continue;
            }
            int inter = 0;
            for (String t : qTokens) {
                if (dTokens.contains(t)) {
                    inter++;
                }
            }
            if (inter == 0) {
                continue;
            }
            int union = qTokens.size() + dTokens.size() - inter;
            double j = (double) inter / (double) union;
            scored.add(new Hit(e.getKey(), e.getValue(), j));
        }
        scored.sort((a, b) -> Double.compare(b.score, a.score));
        Json hits = Json.array();
        for (int i = 0; i < Math.min(k, scored.size()); i++) {
            Hit h = scored.get(i);
            Json o = Json.object()
                    .put("id", h.id)
                    .put("score", h.score)
                    .put("preview", preview(h.content));
            hits.add(o);
        }
        return Json.object().put("ok", true).put("hits", hits);
    }

    public Json link(Json req) {
        String src = req.str("src");
        String dst = req.str("dst");
        if (src == null || dst == null) {
            return Json.object().put("ok", false)
                    .put("error", "missing src/dst");
        }
        outgoing.computeIfAbsent(src, k -> ConcurrentHashMap.newKeySet())
                .add(dst);
        return Json.object().put("ok", true)
                .put("src", src).put("dst", dst);
    }

    public Json neighbors(Json req) {
        String src = req.str("src");
        if (src == null) {
            return Json.object().put("ok", false)
                    .put("error", "missing src");
        }
        Set<String> set = outgoing.get(src);
        Json out = Json.object().put("ok", true).put("count",
                set == null ? 0 : set.size());
        Json arr = Json.array();
        if (set != null) {
            for (String s : set) {
                arr.add(s);
            }
        }
        out.put("neighbors", arr);
        return out;
    }

    public String size() {
        return Json.object().put("ok", true)
                .put("docs", docs.size())
                .put("links", linkCount())
                .toJson();
    }

    public int docCount() {
        return docs.size();
    }

    public int linkCount() {
        int n = 0;
        for (Set<String> s : outgoing.values()) {
            n += s.size();
        }
        return n;
    }

    private static Set<String> tokenize(String s) {
        Set<String> out = new HashSet<>();
        if (s == null) {
            return out;
        }
        int n = s.length();
        int i = 0;
        while (i < n) {
            while (i < n && !isWordChar(s.charAt(i))) {
                i++;
            }
            int start = i;
            while (i < n && isWordChar(s.charAt(i))) {
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

    private static boolean isWordChar(char c) {
        return Character.isLetterOrDigit(c) || c == '_';
    }

    private static String preview(String s) {
        if (s.length() <= 160) {
            return s;
        }
        return s.substring(0, 157) + "...";
    }

    private static final class Hit {
        final String id;
        final String content;
        final double score;

        Hit(String id, String content, double score) {
            this.id = id;
            this.content = content;
            this.score = score;
        }
    }
}
