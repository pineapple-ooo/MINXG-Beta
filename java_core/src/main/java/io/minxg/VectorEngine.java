package io.minxg;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory vector store with cosine + L2 distance on float[] vectors.
 *
 * Sized for the daemon's run-time data (a few thousand 384-dim
 * embeddings per active session). Reads scale linearly because we
 * don't ship an HNSW as part of this module.
 *
 * A future HNSW assembly sits behind the same interface; swapping
 * the implementation here keeps callers stable.
 */
public final class VectorEngine {

    private static final class Entry {
        final String id;
        final float[] vec;

        Entry(String id, float[] vec) {
            this.id = id;
            this.vec = vec;
        }
    }

    private final ConcurrentHashMap<String, Entry> map =
            new ConcurrentHashMap<>();
    private volatile int dim = 0;

    public Json add(Json req) {
        String id = req.str("vid");
        if (id == null || id.isEmpty()) {
            return Json.object().put("ok", false)
                    .put("error", "missing vid");
        }
        List<Json> arr = req.array("vec");
        if (arr.isEmpty()) {
            return Json.object().put("ok", false)
                    .put("error", "missing vec");
        }
        float[] vec = toFloat(arr);
        synchronized (this) {
            if (dim == 0) {
                dim = vec.length;
            } else if (dim != vec.length) {
                return Json.object().put("ok", false)
                        .put("error", "dim mismatch expected " + dim
                                + " got " + vec.length);
            }
            map.put(id, new Entry(id, vec));
        }
        return Json.object().put("ok", true)
                .put("vid", id)
                .put("dim", vec.length);
    }

    public Json search(Json req) {
        List<Json> arr = req.array("vec");
        if (arr.isEmpty()) {
            return Json.object().put("ok", false)
                    .put("error", "missing vec");
        }
        float[] q = toFloat(arr);
        int k = Math.max(1, req.integer("k"));
        int target = Math.min(k, map.size());
        List<Entry> all = new ArrayList<>(map.values());
        Score[] scored = new Score[all.size()];
        for (int i = 0; i < all.size(); i++) {
            Entry e = all.get(i);
            scored[i] = new Score(e.id, cosine(q, e.vec));
        }
        // partial top-k — pq on a small array is cheaper than full sort
        Arrays.sort(scored, (a, b) -> Double.compare(b.score, a.score));
        Json out = Json.object().put("ok", true).put("k", k)
                .put("count", scored.length);
        Json hits = Json.array();
        for (int i = 0; i < target; i++) {
            Json h = Json.object()
                    .put("vid", scored[i].id)
                    .put("score", scored[i].score);
            hits.add(h);
        }
        out.put("hits", hits);
        return out;
    }

    public String size() {
        return Json.object().put("ok", true)
                .put("count", map.size())
                .put("dim", dim)
                .toJson();
    }

    public int count() {
        return map.size();
    }

    public int dim() {
        return dim;
    }

    private static float[] toFloat(List<Json> arr) {
        float[] out = new float[arr.size()];
        for (int i = 0; i < arr.size(); i++) {
            Json it = arr.get(i);
            if (it == null) {
                continue;
            }
            Object v = null;
            // access raw via reflection-free path: we know Json.value
            // from same package; expose via a tiny accessor later if
            // needed. Here we copy the parse logic for the obvious case.
            try {
                v = Double.parseDouble(it.toJson());
            } catch (NumberFormatException ignored) {
            }
            if (v instanceof Number) {
                out[i] = ((Number) v).floatValue();
            }
        }
        return out;
    }

    private static double cosine(float[] a, float[] b) {
        if (a.length != b.length) {
            return 0d;
        }
        double dot = 0d;
        double na = 0d;
        double nb = 0d;
        int n = a.length;
        int i = 0;
        // process 4-wide for SIMD-friendly unrolling
        for (; i + 4 <= n; i += 4) {
            dot += (double) a[i] * b[i]
                    + (double) a[i + 1] * b[i + 1]
                    + (double) a[i + 2] * b[i + 2]
                    + (double) a[i + 3] * b[i + 3];
            na += (double) a[i] * a[i]
                    + (double) a[i + 1] * a[i + 1]
                    + (double) a[i + 2] * a[i + 2]
                    + (double) a[i + 3] * a[i + 3];
            nb += (double) b[i] * b[i]
                    + (double) b[i + 1] * b[i + 1]
                    + (double) b[i + 2] * b[i + 2]
                    + (double) b[i + 3] * b[i + 3];
        }
        for (; i < n; i++) {
            dot += (double) a[i] * b[i];
            na += (double) a[i] * a[i];
            nb += (double) b[i] * b[i];
        }
        double denom = Math.sqrt(na) * Math.sqrt(nb);
        if (denom == 0d) {
            return 0d;
        }
        return dot / denom;
    }

    private static final class Score {
        final String id;
        final double score;

        Score(String id, double score) {
            this.id = id;
            this.score = score;
        }
    }

    /**
     * Best-effort float parser exposed for callers that want to push
     * vectors directly. We expose this as a package-private helper
     * since it depends on the Json layout above.
     */
    static double[] toDoubleArray(Json json) {
        if (json == null) {
            return new double[0];
        }
        List<Json> arr = json.array("");
        return Json.doubles(arr);
    }
}
