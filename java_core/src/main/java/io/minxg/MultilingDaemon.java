package io.minxg;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Service entry point — runs the JVM-side daemon on a TCP port.
 *
 * Protocol: newline-delimited JSON, one request per line, one reply
 * per line. Stats:
 *   {"op":"ping"}                                -> {"ok":true,...} heartbeat
 *   {"op":"v.add","vid":"...","vec":[..]}        -> vector.add
 *   {"op":"v.search","vec":[..],"k":5}           -> vector.search
 *   {"op":"k.put","did":"...","content":"..."}   -> knowledge.put
 *   {"op":"k.query","q":"...","k":5}             -> knowledge.query
 *   {"op":"mem.append","sid":"...","turn":...}   -> session memory
 *   {"op":"mem.recall","sid":"...","k":8}        -> session memory
 *   {"op":"stats"}                               -> full snapshot
 *
 * The Python umbrella process owns startup; we don't expose a
 * standalone entry point here. See MultilingDaemonLauncher in
 * python side for the spawn sequence.
 */
public final class MultilingDaemon {

    private final int port;
    private final ServerSocket serverSocket;
    private final ExecutorService pool;
    private final AtomicBoolean running = new AtomicBoolean(false);

    private final VectorEngine vectors;
    private final KnowledgeGraph knowledge;
    private final SessionMemory memory;
    private final PersistentLog log;

    public MultilingDaemon(int port) throws IOException {
        this.port = port;
        this.serverSocket = new ServerSocket(port);
        this.pool = Executors.newFixedThreadPool(8, r -> {
            Thread t = new Thread(r, "minxg-conn");
            t.setDaemon(true);
            return t;
        });
        this.vectors = new VectorEngine();
        this.knowledge = new KnowledgeGraph();
        this.memory = new SessionMemory();
        this.log = new PersistentLog();
    }

    public int port() {
        return port;
    }

    public void start() {
        if (!running.compareAndSet(false, true)) {
            throw new IllegalStateException("daemon already running");
        }
        Thread accept = new Thread(this::acceptLoop,
                "minxg-daemon");
        accept.setDaemon(true);
        accept.start();
    }

    public void stop() {
        if (!running.compareAndSet(true, false)) {
            return;
        }
        try {
            serverSocket.close();
        } catch (IOException ignored) {
        }
        pool.shutdown();
        try {
            pool.awaitTermination(2, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private void acceptLoop() {
        while (running.get()) {
            try {
                Socket conn = serverSocket.accept();
                conn.setSoTimeout(30_000);
                pool.execute(() -> handleConnection(conn));
            } catch (IOException e) {
                if (running.get()) {
                    // transient — accept loop survives
                }
            }
        }
    }

    private void handleConnection(Socket conn) {
        try (Socket c = conn;
             InputStream in = c.getInputStream();
             OutputStream out = c.getOutputStream()) {
            LineReader lines = new LineReader(in);
            while (running.get()) {
                String line = lines.readLine();
                if (line == null) {
                    return;
                }
                String reply;
                try {
                    reply = dispatch(line);
                } catch (Exception e) {
                    reply = "{\"ok\":false,\"error\":\""
                            + escape(e.toString()) + "\"}";
                }
                out.write(reply.getBytes(StandardCharsets.UTF_8));
                out.write('\n');
                out.flush();
            }
        } catch (IOException e) {
            // peer closed connection
        }
    }

    /** Single dispatch on a JSON request; replies with a JSON string. */
    String dispatch(String line) {
        Json req = Json.parse(line);
        String op = req.str("op");
        if (op == null || op.isEmpty()) {
            return "{\"ok\":false,\"error\":\"missing op\"}";
        }
        switch (op) {
            case "ping":
                return "{\"ok\":true,\"pong\":true,"
                        + "\"java\":\"" + escape(System.getProperty(
                            "java.version"))
                        + "\"}";
            case "v.add":
                return vectors.add(req).toJson();
            case "v.search":
                return vectors.search(req).toJson();
            case "v.size":
                return vectors.size();
            case "k.put":
                return knowledge.put(req).toJson();
            case "k.query":
                return knowledge.query(req).toJson();
            case "k.size":
                return knowledge.size();
            case "k.link":
                return knowledge.link(req).toJson();
            case "k.neighbors":
                return knowledge.neighbors(req).toJson();
            case "mem.append":
                return memory.append(req).toJson();
            case "mem.recall":
                return memory.recall(req).toJson();
            case "mem.list":
                return memory.listSessions();
            case "log.append":
                return log.append(req).toJson();
            case "log.query":
                return log.query(req).toJson();
            case "stats":
                return stats();
            default:
                return "{\"ok\":false,\"error\":\"unknown op:" + escape(op) + "\"}";
        }
    }

    private String stats() {
        Json s = Json.object()
                .put("ok", true)
                .put("vectors.count", vectors.count())
                .put("vectors.dim", vectors.dim())
                .put("knowledge.docs", knowledge.docCount())
                .put("knowledge.links", knowledge.linkCount())
                .put("memory.sessions", memory.sessionCount())
                .put("log.entries", log.entryCount())
                .put("heap.mb",
                        (Runtime.getRuntime().totalMemory()
                                - Runtime.getRuntime().freeMemory())
                                / (1024L * 1024L));
        return s.toJson();
    }

    private static String escape(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n");
    }
}
