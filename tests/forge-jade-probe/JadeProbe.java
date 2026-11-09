package dev.psa.jadeprobe;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import net.minecraft.client.Minecraft;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;

/** Test-only bounded observer. Never changes a query or claims rendering/interaction success. */
@Mod("psajadeprobe")
public final class JadeProbe {
    private static long queries, shipQueries, worldQueries;
    private static double maximumSpan;
    private static final JsonArray SAMPLES = new JsonArray();

    public static void returned(Vec3 start, Vec3 end, AABB box) {
        HitResult cached = Minecraft.getInstance().hitResult;
        boolean storageHit = cached != null && cached.getLocation().distanceToSqr(end) > 10000;
        queries++;
        boolean first = storageHit ? shipQueries++ == 0 : worldQueries++ == 0;
        double span = Math.max(box.getXsize(), Math.max(box.getYsize(), box.getZsize()));
        maximumSpan = Math.max(maximumSpan, span);
        if (first || queries % 100 == 0 || span > 1000) {
            if (SAMPLES.size() < 8 && (first || span > 1000)) {
                JsonObject sample = new JsonObject();
                sample.addProperty("query", queries);
                sample.addProperty("cached_location_differs_from_world_end", storageHit);
                sample.add("world_start", vector(start));
                sample.add("world_end", vector(end));
                sample.addProperty("aabb_max_axis_span", span);
                if (cached != null) sample.add("unchanged_cached_hit_location", vector(cached.getLocation()));
                SAMPLES.add(sample);
            }
            JsonObject report = new JsonObject();
            report.addProperty("scope", "Actual Jade entity-query RETURN observations; category is a coordinate-difference diagnostic, not a frame lookup proof.");
            report.addProperty("queries_returned", queries);
            report.addProperty("cached_storage_like_queries_returned", shipQueries);
            report.addProperty("ordinary_queries_returned", worldQueries);
            report.addProperty("maximum_observed_aabb_axis_span", maximumSpan);
            report.add("bounded_samples", SAMPLES);
            Path output = FMLPaths.GAMEDIR.get().resolve("logs/psa-jade-coordinates.json");
            Path temporary = output.resolveSibling("psa-jade-coordinates.json.tmp");
            try {
                Files.createDirectories(output.getParent());
                Files.writeString(temporary, new GsonBuilder().setPrettyPrinting().create().toJson(report));
                Files.move(temporary, output, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (IOException failure) {
                throw new IllegalStateException("Could not persist Jade query observation", failure);
            }
        }
    }

    private static JsonArray vector(Vec3 point) {
        JsonArray values = new JsonArray();
        values.add(point.x); values.add(point.y); values.add(point.z);
        return values;
    }
}
