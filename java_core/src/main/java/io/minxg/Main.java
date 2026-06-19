package io.minxg;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Standalone daemon entry point. The Python umbrella process uses
 * io.minxg.MultilingDaemon directly; this Main is for ad-hoc local
 * debugging:
 *
 *   java -cp classpath io.minxg.Main [port]
 */
public final class Main {

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 29950;
        MultilingDaemon d = new MultilingDaemon(port);
        d.start();
        System.out.println("multiling java daemon listening on "
                + d.port());
        Runtime.getRuntime().addShutdownHook(new Thread(d::stop));
        // park the main thread
        AtomicBoolean parked = new AtomicBoolean(true);
        while (parked.get()) {
            Thread.sleep(60_000);
        }
    }
}
