package io.minxg;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/**
 * Reads one CRLF- or LF-delimited line at a time from a stream. Blocks
 * until a full line is in or the underlying stream closes.
 *
 * The MultilingDaemon is a line-based RPC; this lets the dispatch
 * loop see complete JSON requests without buffering the whole request
 * in memory.
 */
final class LineReader {

    private final InputStream in;
    private final StringBuilder pending = new StringBuilder();

    LineReader(InputStream in) {
        this.in = in;
    }

    String readLine() throws IOException {
        int read;
        while ((read = in.read()) != -1) {
            char c = (char) read;
            if (c == '\n') {
                String out = pending.toString();
                pending.setLength(0);
                if (!out.isEmpty() && out.charAt(out.length() - 1) == '\r') {
                    out = out.substring(0, out.length() - 1);
                }
                return out;
            }
            pending.append(c);
            // cap a single line to keep memory bounded under attack
            if (pending.length() > 8 * 1024 * 1024) {
                throw new IOException("line exceeded 8 MiB");
            }
        }
        if (pending.length() == 0) {
            return null;
        }
        String out = pending.toString();
        pending.setLength(0);
        return out;
    }
}
