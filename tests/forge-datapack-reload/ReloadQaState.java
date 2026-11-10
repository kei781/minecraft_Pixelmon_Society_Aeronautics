package dev.psa.datapackreloadqa;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraft.server.MinecraftServer;

/** Observes the ORIGINAL server reload future; never replaces it or converts failure into success. */
public final class ReloadQaState {
    private static final AtomicInteger calls = new AtomicInteger();
    private ReloadQaState() { }
    public static void observe(MinecraftServer server, CompletableFuture<?> original) {
        if (calls.incrementAndGet() > 32 || original == null) throw new IllegalStateException("Bounded actual reload observation required");
        UUID run = UUID.randomUUID(); long start = System.nanoTime();
        var begin = row(run, "native_reload_future_observed", server); save(run, "begin", begin);
        original.whenComplete((ignored, failure) -> {
            var done = row(run, failure == null ? "native_reload_completed" : "native_reload_failed", server);
            done.addProperty("elapsed_ms_after_return", (System.nanoTime() - start) / 1000000);
            if (failure != null) {
                while ((failure instanceof java.util.concurrent.CompletionException
                        || failure instanceof java.util.concurrent.ExecutionException) && failure.getCause() != null)
                    failure = failure.getCause();
                done.addProperty("error_class", failure.getClass().getName());
                var frames = new com.google.gson.JsonArray();
                for (var frame : failure.getStackTrace()) {
                    if (frames.size() == 8) break;
                    frames.add(frame.getClassName() + "." + frame.getMethodName());
                }
                done.add("public_stack_method_names", frames);
            }
            save(run, "complete", done);
        });
    }
    private static JsonObject row(UUID run, String event, MinecraftServer server) {
        var data = new JsonObject(); data.addProperty("run", run.toString()); data.addProperty("event", event);
        data.addProperty("observed_at_epoch_ms", System.currentTimeMillis());
        data.addProperty("native_player_count", server.getPlayerCount());
        data.addProperty("thread", Thread.currentThread().getName());
        data.addProperty("original_future_not_replaced", true); return data;
    }
    private static void save(UUID run, String phase, JsonObject data) {
        try {
            Path directory = Path.of("psa-datapack-reload-results"); Files.createDirectories(directory);
            Files.writeString(directory.resolve(run + "-" + phase + ".json"),
                new GsonBuilder().setPrettyPrinting().create().toJson(data) + "\n",
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        } catch (java.io.IOException failure) { throw new IllegalStateException("Native reload evidence write failed", failure); }
    }
}
