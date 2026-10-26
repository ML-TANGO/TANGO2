package edu.anu.spice;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Long-running SPICE scorer with a stdin/stdout RPC loop (adapted from the
 * autogrow docker_spice server).
 *
 * Why: {@code java -jar spice-1.0.jar ...} pays a fresh JVM start and a fresh
 * Stanford CoreNLP load (~5 s) on every call. Keeping one JVM and one
 * SpiceScorer alive amortizes that cost over all holdout evaluations.
 *
 * Usage: {@code java -cp <this>:spice-1.0.jar:lib/* edu.anu.spice.SpiceServer [cache_dir]}
 *   With a cache dir, parsed tuples are cached in LMDB (lmdbjni: x86_64 only).
 *   Without it nothing is cached, which also runs on arm64.
 *   SPICE_THREADS (env, default 4) caps the parser threads. SPICE's own default
 *   is one per processor, and when the parses of many threads do not fit in the
 *   heap, CoreNLP drops sentences ("ran out of memory ... will ignore and
 *   continue"): those tuples go missing and the same pair scores lower, by a
 *   different amount on every run.
 *
 * Protocol (one request per line on stdin):
 *   {@code <input_path>\t<output_path>\n}  (SPICE's JSON input/output files)
 * Server replies one line on stdout:
 *   {@code {"event":"done","elapsed_ms":N}}  OR  {@code {"event":"error","msg":"..."}}
 * After start-up it prints {@code {"event":"ready"}}; {@code EXIT\n} stops it.
 */
public class SpiceServer {

    public static void main(String[] args) throws IOException {
        String cacheDir = args.length > 0 ? args[0] : null;

        // SpiceScorer prints "SPICE evaluation took: ..." to System.out even
        // under -silent, which would corrupt the line protocol: keep the real
        // stdout for replies and send everything else to stderr.
        PrintStream protocolOut = System.out;
        System.setOut(System.err);

        String threads = System.getenv("SPICE_THREADS");
        if (threads == null || !threads.matches("[1-9][0-9]*")) threads = "4";

        SpiceScorer scorer = new SpiceScorer();
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));

        protocolOut.println("{\"event\":\"ready\"}");
        protocolOut.flush();

        String line;
        while ((line = reader.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) continue;
            if (line.equals("EXIT")) break;

            String[] parts = line.split("\t", 2);
            if (parts.length != 2) {
                protocolOut.println("{\"event\":\"error\",\"msg\":\"bad request: expected <in>\\\\t<out>\"}");
                protocolOut.flush();
                continue;
            }
            List<String> cliArgs = new ArrayList<String>(Arrays.asList(parts[0], "-out", parts[1], "-subset", "-silent",
                    "-threads", threads));
            if (cacheDir != null) {
                cliArgs.add("-cache");
                cliArgs.add(cacheDir);
            }
            long t0 = System.currentTimeMillis();
            try {
                scorer.scoreBatch(new SpiceArguments(cliArgs.toArray(new String[0])));
                long elapsed = System.currentTimeMillis() - t0;
                protocolOut.println("{\"event\":\"done\",\"elapsed_ms\":" + elapsed + "}");
            } catch (Throwable t) {
                String msg = t.getMessage() != null ? t.getMessage() : t.toString();
                msg = msg.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ").replace("\r", " ");
                protocolOut.println("{\"event\":\"error\",\"msg\":\"" + msg + "\"}");
            }
            protocolOut.flush();
        }
    }
}
