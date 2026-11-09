package dev.psa.pixelmonfixture;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.pixelmonmod.pixelmon.api.pokemon.PokemonBuilder;
import com.pixelmonmod.pixelmon.api.pokemon.stats.BattleStatsType;
import com.pixelmonmod.pixelmon.battles.controller.participants.WildPixelmonParticipant;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.UUID;
import net.minecraftforge.fml.loading.FMLPaths;

/** Native query arithmetic with fixed inputs; no world actors, battle or player input. */
public final class HitpointControls {
    private HitpointControls() { }

    public static Path run() throws java.io.IOException {
        var rows = new JsonArray(); int failures = 0;
        for (String species : new String[]{"shedinja", "magikarp", "ditto"})
            for (int level : new int[]{1, 50, 100}) for (int dynamax : new int[]{0, 10}) {
                JsonObject row = sample(species, level, dynamax, false);
                rows.add(row); if (!row.get("pass").getAsBoolean()) failures++;
            }
        for (int dynamax : new int[]{0, 10}) {
            JsonObject row = sample("shedinja", 100, dynamax, true);
            rows.add(row); if (!row.get("pass").getAsBoolean()) failures++;
        }
        var report = new JsonObject(); report.addProperty("run", UUID.randomUUID().toString());
        report.addProperty("time", Instant.now().toString());
        report.addProperty("scope", "Native HP getters on virtual participants with fixed IV/EV/levels and explicit wrapper state; not actual Dynamax input or a battle");
        report.addProperty("cases", rows.size()); report.addProperty("failures", failures);
        report.addProperty("pass", failures == 0); report.add("rows", rows);
        Path directory = FMLPaths.GAMEDIR.get().resolve("psa-pixelmon-hp-controls");
        Files.createDirectories(directory);
        Path output = directory.resolve(report.get("run").getAsString() + ".json");
        Files.writeString(output, new GsonBuilder().setPrettyPrinting().create().toJson(report) + "\n",
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        return output;
    }

    private static JsonObject sample(String species, int level, int dynamax, boolean customHP) {
        var pokemon = PokemonBuilder.builder().species(species).level(level)
            .ivs(0, 0, 0, 0, 0, 0).evs(0, 0, 0, 0, 0, 0).build();
        pokemon.setDynamaxLevel(dynamax);
        if (customHP) pokemon.getStats().set(BattleStatsType.HP, 100);
        var wrapper = new WildPixelmonParticipant(pokemon).asWrapper();
        int expectedBase;
        if (customHP) expectedBase = 100;
        else if (species.equals("shedinja")) expectedBase = 1;
        else expectedBase = (species.equals("magikarp") ? 40 : 96) * level / 100 + level + 10;
        int expectedDynamax = species.equals("shedinja") && !customHP ? 1
            : expectedBase + (int) Math.ceil(expectedBase * (0.5D + dynamax * 0.05D));
        wrapper.isDynamax = -1;
        int normal = wrapper.getMaxHealth(false), baseNormal = wrapper.getMaxHealth(true);
        wrapper.isDynamax = 1;
        int active = wrapper.getMaxHealth(false), baseActive = wrapper.getMaxHealth(true);
        wrapper.isDynamax = 0;
        int ended = wrapper.getMaxHealth(false);
        var row = new JsonObject(); row.addProperty("species", species); row.addProperty("level", level);
        row.addProperty("dynamax_level", dynamax); row.addProperty("custom_base_hp", customHP);
        row.addProperty("expected_base", expectedBase); row.addProperty("expected_active", expectedDynamax);
        row.addProperty("normal", normal); row.addProperty("base_normal", baseNormal);
        row.addProperty("active", active); row.addProperty("base_active", baseActive); row.addProperty("ended", ended);
        row.addProperty("pass", normal == expectedBase && baseNormal == expectedBase && baseActive == expectedBase
            && ended == expectedBase && active == expectedDynamax);
        return row;
    }
}
