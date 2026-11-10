package dev.psa.aliresync;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.yanny.aci.manager.CorePluginManager;
import com.yanny.aci.tooltip.TooltipNodePalette;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/** Disposable instrumentation. Observes real encode/decode/mutation threads without changing native data. */
public final class TraceState {
    private static final String RUN = UUID.randomUUID().toString();
    private static final AtomicInteger sequence = new AtomicInteger();
    private static final java.util.concurrent.atomic.AtomicReference<String> armedStress = new java.util.concurrent.atomic.AtomicReference<>();
    private static final ConcurrentHashMap<TooltipNodePalette, Stats> stats = new ConcurrentHashMap<>();
    private static final Set<String> METHODS = Set.of("decode", "encode", "getOrCreate", "getNodeId", "getNodeById", "clear");
    private static final class Stats {
        final AtomicInteger active = new AtomicInteger(), epoch = new AtomicInteger();
        final AtomicInteger registrations = new AtomicInteger();
        final AtomicLong activeThread = new AtomicLong(), decodeThread = new AtomicLong(), registrationThread = new AtomicLong();
        final ConcurrentHashMap<String, AtomicLong> calls = new ConcurrentHashMap<>();
        volatile boolean decoding, overlap;
        volatile AliPaletteFingerprint.Snapshot decoded;
    }
    private TraceState() { }
    private static Stats state(TooltipNodePalette palette) {
        if (stats.size() > 32) throw new IllegalStateException("Palette observation bound exceeded");
        return stats.computeIfAbsent(palette, ignored -> new Stats());
    }

    public static void beginDecode(TooltipNodePalette palette) {
        var state = state(palette); state.epoch.incrementAndGet(); state.decodeThread.set(Thread.currentThread().getId());
        if (state.registrations.get() > 0 && state.registrationThread.get() != Thread.currentThread().getId()) state.overlap = true;
        state.decoding = true; var data = event("decode_begin", palette); save(data);
    }
    public static void endDecode(TooltipNodePalette palette) {
        var state = state(palette); var snapshot = AliPaletteFingerprint.capture(palette, -1);
        state.decoded = snapshot; state.decoding = false;
        var data = event("decode_complete", palette); fingerprint(data, snapshot); save(data);
    }
    public static void beforeEncode(TooltipNodePalette palette) {
        var data = event("encode_prefix", palette); fingerprint(data, AliPaletteFingerprint.capture(palette, -1)); save(data);
    }
    public static void beginCreate(TooltipNodePalette palette) {
        var state = state(palette); long thread = Thread.currentThread().getId();
        int previous = state.active.getAndIncrement();
        if (previous == 0) state.activeThread.set(thread);
        if ((previous > 0 && state.activeThread.get() != thread)
                || (state.decoding && state.decodeThread.get() != thread)) state.overlap = true;
        String name = Thread.currentThread().getName();
        long count = state.calls.computeIfAbsent(name, ignored -> new AtomicLong()).incrementAndGet();
        if (count == 1) save(event("first_native_create_on_thread", palette));
    }
    public static void endCreate(TooltipNodePalette palette) {
        if (state(palette).active.decrementAndGet() < 0) throw new IllegalStateException("Unbalanced native create trace");
    }
    public static void beginRegistration() {
        var registry = CorePluginManager.INSTANCE.clientRegistry;
        if (registry == null) return;
        var palette = registry.getTooltipCache(); var state = state(palette);
        int previous = state.registrations.getAndIncrement();
        long thread = Thread.currentThread().getId();
        if (previous == 0) state.registrationThread.set(thread);
        if ((state.decoding && state.decodeThread.get() != thread)
                || (previous > 0 && state.registrationThread.get() != thread)) state.overlap = true;
        save(event("registration_begin", palette));
        String stress = armedStress.getAndSet(null);
        if (stress != null) {
            scheduleStress(stress, palette);
            // Explicit QA-only artificial delay, never part of the production compatibility jar.
            // Do not wait for the render thread while holding its requested palette monitor.
            java.util.concurrent.locks.LockSupport.parkNanos(java.util.concurrent.TimeUnit.SECONDS.toNanos(1));
        }
    }

    public static void armStress(String action) {
        if (!List.of("render", "disconnect").contains(action) || !armedStress.compareAndSet(null, action))
            throw new IllegalStateException("One closed QA stress action required");
    }

    private static void scheduleStress(String action, TooltipNodePalette palette) {
        try {
            ClassLoader loader = palette.getClass().getClassLoader();
            Class<?> type = loader.loadClass("net.minecraft.client.Minecraft");
            Object client = type.getMethod("m_91087_").invoke(null);
            long queued = System.nanoTime();
            ((java.util.concurrent.Executor) client).execute(() -> {
                var started = event(action + "_stress_render_begin", palette);
                started.addProperty("queued_wait_ms", (System.nanoTime() - queued) / 1000000); save(started);
                try {
                    if (action.equals("render")) {
                        long before = System.nanoTime(); Object node = palette.getNodeById(0);
                        var done = event("render_stress_native_palette_read_complete", palette);
                        done.addProperty("palette_wait_ms", (System.nanoTime() - before) / 1000000);
                        done.addProperty("native_node_present", node != null); save(done);
                    } else {
                        Class<?> listener = loader.loadClass("net.minecraft.client.multiplayer.ClientPacketListener");
                        Object packetListener = uniqueMethod(type, listener).invoke(client);
                        Class<?> connection = loader.loadClass("net.minecraft.network.Connection");
                        Object network = uniqueMethod(listener, connection).invoke(packetListener);
                        Class<?> component = loader.loadClass("net.minecraft.network.chat.Component");
                        Object reason = component.getMethod("m_237113_", String.class).invoke(null, "PSA owned ALI registration disconnect QA");
                        uniqueMethod(connection, void.class, component).invoke(network, reason);
                        save(event("disconnect_stress_native_disconnect_requested", palette));
                    }
                } catch (Throwable failure) {
                    while (failure instanceof java.lang.reflect.InvocationTargetException && failure.getCause() != null) failure = failure.getCause();
                    if (failure instanceof VirtualMachineError fatal) throw fatal;
                    if (failure instanceof ThreadDeath fatal) throw fatal;
                    var failed = event(action + "_stress_failed", palette);
                    failed.addProperty("error_class", failure.getClass().getName()); save(failed);
                }
            });
        } catch (ReflectiveOperationException failure) {
            throw new IllegalStateException("Pinned native QA stress API required", failure);
        }
    }

    private static java.lang.reflect.Method uniqueMethod(Class<?> owner, Class<?> result, Class<?>... arguments) {
        var methods = java.util.Arrays.stream(owner.getMethods()).filter(method -> !java.lang.reflect.Modifier.isStatic(method.getModifiers())
            && method.getReturnType() == result && java.util.Arrays.equals(method.getParameterTypes(), arguments)).toList();
        if (methods.size() != 1) throw new IllegalStateException("Unique pinned native QA API required");
        return methods.get(0);
    }
    public static void endRegistration() {
        var registry = CorePluginManager.INSTANCE.clientRegistry;
        if (registry == null) return;
        var palette = registry.getTooltipCache(); var state = state(palette);
        if (state.registrations.decrementAndGet() < 0) throw new IllegalStateException("Unbalanced registration trace");
        save(event("registration_complete", palette));
    }
    public static void captureClient(String label) {
        if (!List.of("before_reload", "after_reload", "final").contains(label))
            throw new IllegalArgumentException("Known snapshot label required");
        var registry = CorePluginManager.INSTANCE.clientRegistry;
        if (registry == null) throw new IllegalStateException("Actual client registry required");
        var palette = registry.getTooltipCache();
        synchronized (palette) {
            var state = state(palette); var decoded = state.decoded;
            if (decoded == null) throw new IllegalStateException("Actual decode trace required");
            var now = AliPaletteFingerprint.capture(palette, decoded.nodes());
            var data = event(label, palette); fingerprint(data, now);
            data.addProperty("matches_last_decode", now.equals(decoded));
            var total = AliPaletteFingerprint.capture(palette, -1); data.addProperty("total_nodes", total.nodes());
            var threads = new JsonObject(); state.calls.forEach((name, count) -> threads.addProperty(name, count.get()));
            data.add("native_create_threads", threads); save(data);
        }
    }

    private static JsonObject event(String kind, TooltipNodePalette palette) {
        var state = state(palette); var data = new JsonObject(); data.addProperty("event", kind);
        data.addProperty("observed_at_epoch_ms", System.currentTimeMillis());
        data.addProperty("run", RUN); data.addProperty("epoch", state.epoch.get());
        data.addProperty("palette_identity", Integer.toHexString(System.identityHashCode(palette)));
        data.addProperty("thread", Thread.currentThread().getName()); data.addProperty("thread_id", Thread.currentThread().getId());
        data.addProperty("palette_monitor_held", Thread.holdsLock(palette)); data.addProperty("overlap_observed", state.overlap);
        data.addProperty("active_native_create_calls", state.active.get());
        data.addProperty("active_registrations", state.registrations.get());
        var locks = new JsonObject();
        for (var method : palette.getClass().getDeclaredMethods()) if (METHODS.contains(method.getName()))
            locks.addProperty(method.getName(), java.lang.reflect.Modifier.isSynchronized(method.getModifiers()));
        data.add("native_method_synchronized_flags", locks); return data;
    }
    private static void fingerprint(JsonObject data, AliPaletteFingerprint.Snapshot snapshot) {
        data.addProperty("ordered_native_nodes", snapshot.nodes()); data.addProperty("ordered_semantic_sha256", snapshot.sha256());
        data.addProperty("transport_indexed_key_nodes", snapshot.indexedKeyNodes());
    }
    private static void save(JsonObject data) {
        try {
            Path directory = Path.of("psa-ali-resync-trace", RUN); Files.createDirectories(directory);
            Files.writeString(directory.resolve(String.format("%06d-%s.json", sequence.getAndIncrement(), data.get("event").getAsString())),
                new GsonBuilder().setPrettyPrinting().create().toJson(data) + "\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        } catch (java.io.IOException failure) { throw new IllegalStateException("Native resync evidence write failed", failure); }
    }
}
