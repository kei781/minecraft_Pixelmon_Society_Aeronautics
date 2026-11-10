import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.concurrent.TimeUnit;

/** Owned Windows filesystem fixture; never points at a game checkpoint. */
public final class AtomicCheckpointWriter {
    public static void main(String[] args) throws Exception {
        Path folder = Path.of(args[0]).toRealPath();
        if (!Files.readString(folder.resolve(".psa-file-share-test")).trim().equals("psa-atomic-share-fixture-v1"))
            throw new IllegalArgumentException("Owned fixture marker required");
        int iterations = Integer.parseInt(args[1]);
        if (iterations < 1 || iterations > 10000) throw new IllegalArgumentException("Fixture bound required");
        Path destination = folder.resolve("checkpoint.json");
        if (!Files.isRegularFile(destination) || Files.isSymbolicLink(destination))
            throw new IllegalArgumentException("Existing regular fixture required");
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15);
        while (!Files.isRegularFile(folder.resolve("reader-open.signal"))) {
            if (System.nanoTime() > deadline) throw new IllegalStateException("Reader readiness timeout");
            Thread.sleep(5);
        }
        int successful = 0, failed = 0;
        String firstFailure = null;
        for (int index = 0; index < iterations; index++) {
            Path temporary = Files.createTempFile(folder, ".psa-render-", ".tmp");
            try {
                Files.writeString(temporary, "{\"fixture\":true,\"iteration\":" + index + "}\n");
                // Same atomic-replace flags as the authored RenderProbe checkpoint writer.
                Files.move(temporary, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                successful++;
            } catch (Exception failure) {
                failed++;
                if (firstFailure == null) firstFailure = failure.getClass().getName();
            } finally { Files.deleteIfExists(temporary); }
            Thread.sleep(1);
        }
        Files.writeString(folder.resolve("writer-finished.signal"), "done\n");
        System.out.println("{\"fixture\":true,\"iterations\":" + iterations + ",\"successful\":" + successful
                + ",\"failed\":" + failed + ",\"first_failure_type\":"
                + (firstFailure == null ? "null" : "\"" + firstFailure + "\"") + "}");
    }
}
