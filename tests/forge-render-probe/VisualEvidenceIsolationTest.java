package dev.psa.renderprobe;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Modifier;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.BlockingQueue;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.world.entity.Entity;
import static dev.psa.renderprobe.RenderProtocol.*;

/** Real client queue rejection without starting Minecraft; not a native visual/render test. */
public final class VisualEvidenceIsolationTest {
    public static void main(String[] args) throws Exception {
        Class<?> client = Class.forName("dev.psa.renderprobe.RenderClient");
        var batchField = client.getDeclaredField("batch"); batchField.setAccessible(true);
        var sent = client.getDeclaredField("sent"); sent.setAccessible(true); sent.set(null, false);
        if (!Modifier.isVolatile(batchField.getModifiers()) || !Modifier.isVolatile(sent.getModifiers()))
            throw new AssertionError("Worker snapshots need published batch and sent state");
        var mask = client.getDeclaredField("modelObservedMask"); mask.setAccessible(true); mask.setInt(null, 0);
        var queueField = client.getDeclaredField("visualFrames"); queueField.setAccessible(true);
        @SuppressWarnings("unchecked") BlockingQueue<Object> queue = (BlockingQueue<Object>) queueField.get(null);
        var consume = client.getDeclaredMethod("consumeVisualFrames"); consume.setAccessible(true);
        Class<?> frame = Class.forName("dev.psa.renderprobe.RenderClient$VisualFrame");
        var create = frame.getDeclaredConstructor(Batch.class, Entity.class, BakedModel.class, boolean.class);
        create.setAccessible(true);
        UUID run = UUID.randomUUID();
        Token token = new Token(7, UUID.randomUUID(), "create:cardboard_package_10x12", "create:package",
                "com.simibubi.create.content.logistics.box.PackageEntity", true);
        Batch current = new Batch(run, 3, List.of(token)); batchField.set(null, current);
        List<Batch> stale = List.of(new Batch(UUID.randomUUID(), 3, List.of(token)),
                new Batch(run, 2, List.of(token)), new Batch(run, 3, List.of(token)));
        for (Batch previous : stale) {
            // Null entity is a canary: stale data must be rejected before any game entity access.
            queue.add(create.newInstance(previous, null, null, true));
            consume.invoke(null);
            if (!queue.isEmpty() || mask.getInt(null) != 0) throw new AssertionError("Stale frame mutated evidence");
        }
        queue.add(create.newInstance(current, null, null, true));
        try {
            consume.invoke(null);
            throw new AssertionError("Current-packet canary did not reach entity validation");
        } catch (InvocationTargetException expected) {
            if (!(expected.getCause() instanceof NullPointerException)) throw expected;
        }
        batchField.set(null, null); queue.clear();
        System.out.println("PSA_VISUAL_EVIDENCE_PASS published state; stale run/index/equal-packet rejected; current identity validation reachable");
    }
}
