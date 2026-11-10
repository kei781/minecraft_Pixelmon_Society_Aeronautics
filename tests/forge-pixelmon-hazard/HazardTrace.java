package dev.psa.hazardtrace;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.pixelmonmod.pixelmon.api.test.TestResult;
import com.pixelmonmod.pixelmon.battles.controller.participants.PixelmonWrapper;
import com.pixelmonmod.pixelmon.battles.controller.participants.WildPixelmonParticipant;
import com.pixelmonmod.pixelmon.battles.status.EntryHazard;
import com.pixelmonmod.pixelmon.battles.status.Spikes;
import com.pixelmonmod.pixelmon.battles.status.StatusType;
import com.pixelmonmod.pixelmon.battles.status.StealthRock;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.UUID;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.server.ServerLifecycleHooks;

/** Observe the original assertion; optional effects run only after its result exists. */
@Mod("psahazardtrace")
public final class HazardTrace {
    private static final String RUN = UUID.randomUUID().toString();
    private static final JsonArray ROWS = new JsonArray();
    private static final JsonArray PROBES = new JsonArray();
    private static final JsonArray ERRORS = new JsonArray();
    private static WildPixelmonParticipant minior, fish;
    private static TestResult nativeResult;
    private static int checkpoint;
    private static boolean finished;

    public HazardTrace() {
        // Mixin plugin initialization exceptions can disable a config without
        // stopping Forge. The mod entry point must independently fail closed.
        HazardTracePlugin.requireOwnedProfile();
        try { Class.forName(HazardTracePlugin.TARGET); }
        catch (ClassNotFoundException failure) { throw new IllegalStateException("Pinned native test missing", failure); }
        HazardTracePlugin.requireApplied();
    }

    public static void capture(WildPixelmonParticipant participant) {
        HazardTracePlugin.requireOwnedProfile();
        HazardTracePlugin.requireApplied();
        var server = ServerLifecycleHooks.getCurrentServer();
        if (server == null || !server.isDedicatedServer() || server.getPlayerCount() != 0
                || minior != null || participant.getEntity() == null)
            throw new IllegalStateException("One owned world-backed native diagnostic required");
        minior = participant;
        snapshot("created");
    }

    public static void attacks(WildPixelmonParticipant participant) {
        fish = participant;
        snapshot("before_attacks");
    }

    public static void snapshot(String phase) {
        if (minior == null) throw new IllegalStateException("Captured native test required");
        var wrapper = minior.asWrapper();
        var row = new JsonObject(); row.addProperty("phase", phase); row.addProperty("time", Instant.now().toString());
        row.addProperty("health", wrapper.getHealth()); row.addProperty("maximum", wrapper.getMaxHealth());
        row.addProperty("health_percent", wrapper.getHealthPercent()); row.addProperty("on_battlefield", wrapper.onBattlefield);
        row.addProperty("battle_bound", wrapper.bc != null); row.addProperty("meteor_form", wrapper.getForm().isForm("meteor"));
        row.addProperty("ability", wrapper.getAbility().getClass().getSimpleName());
        row.addProperty("spikes", wrapper.hasStatus(StatusType.Spikes));
        row.addProperty("stealth_rock", wrapper.hasStatus(StatusType.StealthRock));
        var statuses = new JsonArray(); for (var status : wrapper.getStatuses()) statuses.add(status.getClass().getSimpleName());
        row.add("statuses", statuses); ROWS.add(row); write(finished ? "finished" : "observing", nativeResult);
    }

    public static void finish(TestResult originalResult) {
        if (finished) throw new IllegalStateException("One native result required");
        nativeResult = originalResult;
        snapshot("after_original_assertion");
        // The native result is already calculated; never replace, complete or mutate it.
        if (Boolean.getBoolean("psa.pixelmonHazardEffects")) {
            try {
                if (fish == null || minior.bc == null || fish.bc != minior.bc || minior.bc.battleEnded)
                    throw new IllegalStateException("Exact still-owned native battle required");
                var wrapper = minior.asWrapper();
                var allow = new JsonObject();
                for (var type : new StatusType[]{StatusType.Spikes, StatusType.StealthRock, StatusType.ToxicSpikes,
                        StatusType.StickyWeb, StatusType.Steelsurge, StatusType.Substitute})
                    allow.addProperty(type.name(), wrapper.getAbility().allowsStatus(type, wrapper, fish.asWrapper()));
                var family = new JsonObject(); family.addProperty("kind", "native_ability_allow_family"); family.add("allowed", allow);
                PROBES.add(family);
                effect("minior_stealth_rock", wrapper, new StealthRock(), true);
                effect("minior_spikes_flying", wrapper, new Spikes(), false);
                effect("magikarp_stealth_rock", fish.asWrapper(), new StealthRock(), true);
                effect("magikarp_spikes", fish.asWrapper(), new Spikes(), true);
            } catch (Throwable failure) {
                if (failure instanceof VirtualMachineError fatal) throw fatal;
                if (failure instanceof ThreadDeath fatal) throw fatal;
                ERRORS.add(failure.toString());
            }
        }
        finished = true; write("finished", originalResult);
    }

    private static void effect(String name, PixelmonWrapper wrapper, EntryHazard hazard, boolean expectedDamage) {
        int old = wrapper.getHealth();
        var row = new JsonObject(); row.addProperty("kind", "post_assert_native_switch_effect"); row.addProperty("name", name);
        try {
            wrapper.setHealth(wrapper.getMaxHealth());
            int before = wrapper.getHealth(); int computed = hazard.getDamage(wrapper);
            hazard.applyEffectOnSwitch(wrapper);
            int after = wrapper.getHealth();
            row.addProperty("before", before); row.addProperty("computed_damage", computed); row.addProperty("after", after);
            row.addProperty("expected_damage", expectedDamage);
            row.addProperty("pass", expectedDamage ? computed > 0 && before - after == computed : before == after);
        } finally {
            wrapper.setHealth(old);
            row.addProperty("health_restored", wrapper.getHealth() == old); PROBES.add(row);
        }
    }

    private static void write(String phase, TestResult originalResult) {
        var report = new JsonObject(); report.addProperty("run", RUN); report.addProperty("phase", phase);
        report.addProperty("scope", "Original native test observed unchanged; separately labelled optional effects after original assertion result, not player input");
        report.addProperty("effects_opted_in", Boolean.getBoolean("psa.pixelmonHazardEffects"));
        report.add("observations", ROWS); report.add("probes", PROBES); report.add("errors", ERRORS);
        if (originalResult != null) {
            report.addProperty("original_native_pass", originalResult.isSuccess());
            report.addProperty("original_native_reason", originalResult.getReason());
        }
        try {
            Path folder = Path.of("psa-pixelmon-hazard-trace", RUN); Files.createDirectories(folder);
            Files.writeString(folder.resolve(String.format("%04d-%s.json", checkpoint++, phase)),
                new GsonBuilder().setPrettyPrinting().create().toJson(report) + "\n",
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        } catch (java.io.IOException failure) { throw new IllegalStateException("Hazard evidence write failed", failure); }
    }
}
