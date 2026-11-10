package dev.psa.renderprobe;

import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.minecraftforge.event.TickEvent;
import static dev.psa.renderprobe.RenderProtocol.*;

/** Actual wait ticks 2..19 must avoid checkpoint I/O and ACK; no Minecraft launch or GPU proof. */
public final class ModelWaitNoWriteTest {
    public static void main(String[] args) throws Exception {
        Class<?> client = Class.forName("dev.psa.renderprobe.RenderClient");
        var batchField = client.getDeclaredField("batch"); batchField.setAccessible(true);
        var sent = client.getDeclaredField("sent"); sent.setAccessible(true); sent.set(null, false);
        Token token = new Token(7, UUID.randomUUID(), "create:cardboard_package_10x12", "create:package",
                "com.simibubi.create.content.logistics.box.PackageEntity", true);
        batchField.set(null, new Batch(UUID.randomUUID(), 0, List.of(token)));
        var returned = client.getDeclaredField("returned"); returned.setAccessible(true);
        @SuppressWarnings("unchecked") Set<Integer> returns = (Set<Integer>) returned.get(null);
        returns.add(0);
        for (String name : List.of("modelObservedMask", "missingMask")) {
            var field = client.getDeclaredField(name); field.setAccessible(true); field.setInt(null, 0);
        }
        var wait = client.getDeclaredField("modelWaitTicks"); wait.setAccessible(true); wait.setInt(null, 1);
        var tick = client.getDeclaredMethod("tick", TickEvent.ClientTickEvent.class);
        for (int expected = 2; expected <= 19; expected++) {
            // Persisting would initialize the Forge game/checkpoint environment, unavailable here.
            tick.invoke(null, new TickEvent.ClientTickEvent(TickEvent.Phase.END));
            if (wait.getInt(null) != expected || sent.getBoolean(null))
                throw new AssertionError("Wait interval changed or premature ACK transition");
        }
        batchField.set(null, null); returns.clear();
        System.out.println("PSA_MODEL_WAIT_PASS actual ticks2..19 do not persist or ACK; first entry/deadline and native GPU untested");
    }
}
