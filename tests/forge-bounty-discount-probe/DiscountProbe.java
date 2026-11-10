package dev.psa.discountprobe;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.nio.file.Files;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;

/** Isolated public factory/function probe; not a client-render or bounty-completion claim. */
@Mod("psadiscountprobe")
public final class DiscountProbe {
    private static final boolean PATCHED = Boolean.getBoolean("psa.discount.patched");
    private static Thread watchedThread;
    private static Integer factoryArgument;
    private static int argumentObservations;
    private int pendingTicks = -1;

    public DiscountProbe() {
        MinecraftForge.EVENT_BUS.addListener(this::started);
        MinecraftForge.EVENT_BUS.addListener(this::tick);
    }

    /** Observer returns the original argument; unrelated world-generation threads are ignored. */
    public static void observeFactoryArgument(int value) {
        if (Thread.currentThread() == watchedThread) {
            factoryArgument = value;
            argumentObservations++;
        }
    }

    private void started(ServerStartedEvent event) { pendingTicks = 20; }

    private void tick(TickEvent.ServerTickEvent event) {
        if (event.phase != TickEvent.Phase.END || pendingTicks < 0 || --pendingTicks != 0) return;
        pendingTicks = -1;
        try {
            Class<?> outer = Class.forName("io.ejekta.bountiful.content.BountyCreator");
            Object companion = outer.getField("Companion").get(null);
            var factory = companion.getClass().getMethod("createBountyItem", ServerLevel.class,
                    BlockPos.class, Set.class, int.class, long.class);
            var discount = companion.getClass().getMethod("getDiscount", int.class);
            ServerLevel level = event.getServer().overworld();
            Set<Integer> inputs = new LinkedHashSet<>();
            for (int i = -30; i <= 30; i++) inputs.add(i);
            for (int i : new int[] {Integer.MIN_VALUE, -32768, -75, -31, 31, 75, 32768, 65536, Integer.MAX_VALUE})
                inputs.add(i);
            JsonArray cases = new JsonArray();
            int inRange = 0;
            int outsideMismatches = 0;
            for (int input : inputs) {
                factoryArgument = null;
                argumentObservations = 0;
                watchedThread = Thread.currentThread();
                Object stack;
                try {
                    // An empty decree set is a real supported factory input; no world/player state is written.
                    stack = factory.invoke(companion, level, level.getSharedSpawnPos(), Set.of(), input, level.getGameTime());
                } finally { watchedThread = null; }
                if (factoryArgument == null || argumentObservations != 1)
                    throw new IllegalStateException("Actual factory constructor argument was not observed once");
                int expectedFactory = input < -30 ? -30 : input > 30 ? 30 : input;
                if (factoryArgument != expectedFactory)
                    throw new IllegalStateException("Pinned server factory reputation range differs");
                double server = (Double) discount.invoke(companion, factoryArgument);
                double displayed = (Double) discount.invoke(companion, input);
                boolean matches = Double.doubleToLongBits(server) == Double.doubleToLongBits(displayed);
                boolean within = input >= -30 && input <= 30;
                if (within) {
                    inRange++;
                    if (!matches) throw new IllegalStateException("An in-range discount changed");
                } else if (!matches) outsideMismatches++;
                if (matches != (PATCHED || within))
                    throw new IllegalStateException("Unexpected baseline/fixed mismatch: " + input);
                JsonObject row = new JsonObject();
                row.addProperty("source_reputation", input);
                row.addProperty("actual_factory_constructor_reputation", factoryArgument);
                row.addProperty("factory_argument_observations", argumentObservations);
                row.addProperty("empty_decree_factory_returned_stack", stack != null);
                row.addProperty("server_multiplier", server);
                row.addProperty("ui_equivalent_multiplier", displayed);
                row.addProperty("matches_actual_server_argument", matches);
                row.addProperty("ui_discount_percent_text", String.format(Locale.ROOT, "%.1f", (1.0 - displayed) * 100.0));
                cases.add(row);
            }
            if (cases.size() != 70 || inRange != 61 || outsideMismatches != (PATCHED ? 0 : 9))
                throw new IllegalStateException("Incomplete counterfactual coverage");
            JsonObject report = new JsonObject();
            report.addProperty("patched", PATCHED);
            report.addProperty("scope", "actual original server factory argument and native discount function; patched client-only mixin applied to common class in isolated headless diagnostic, not real client rendering or production server deployment");
            report.addProperty("in_range_unchanged", inRange);
            report.addProperty("outside_server_ui_mismatches", outsideMismatches);
            report.add("cases", cases);
            var directory = FMLPaths.GAMEDIR.get().resolve("psa-validation");
            Files.createDirectories(directory);
            Files.writeString(directory.resolve("bounty-discount.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report) + "\n");
            System.out.println("PSA_DISCOUNT_PROBE " + (PATCHED ? "PATCHED_PASS" : "BASELINE_REPRODUCED") + " cases=70 in_range=61");
        } catch (Throwable failure) {
            System.err.println("PSA_DISCOUNT_PROBE FAILED");
            failure.printStackTrace();
        } finally {
            watchedThread = null;
            event.getServer().halt(false);
        }
    }
}
