package dev.psa.modelaudit;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.logging.LogUtils;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ModelEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.registries.ForgeRegistries;

/** Opt-in, client-only default-stack model lookup. Never renders, spawns or acknowledges entities. */
@Mod("psamodelaudit")
public final class NativeModelAudit {
    private static final org.slf4j.Logger LOG = LogUtils.getLogger();
    private static volatile int generation;

    @Mod.EventBusSubscriber(modid = "psamodelaudit", value = Dist.CLIENT, bus = Mod.EventBusSubscriber.Bus.MOD)
    public static final class Models {
        @SubscribeEvent
        public static void baked(ModelEvent.BakingCompleted event) { generation++; }
    }

    @Mod.EventBusSubscriber(modid = "psamodelaudit", value = Dist.CLIENT)
    public static final class Client {
        private static int activeGeneration, position, real;
        private static List<ResourceLocation> ids;
        private static JsonArray missing, errors, defaults;
        private static UUID run;

        @SubscribeEvent
        public static void tick(TickEvent.ClientTickEvent event) throws Exception {
            if (event.phase != TickEvent.Phase.END || !Boolean.getBoolean("psa.modelAudit")) return;
            var mc = Minecraft.getInstance();
            if (generation == 0 || mc.getOverlay() != null) return;
            if (activeGeneration != generation) {
                activeGeneration = generation;
                ids = ForgeRegistries.ITEMS.getKeys().stream()
                        .filter(id -> !id.getNamespace().equals("minecraft"))
                        .sorted(java.util.Comparator.comparing(ResourceLocation::toString)).toList();
                position = 0; real = 0; run = UUID.randomUUID();
                missing = new JsonArray(); errors = new JsonArray(); defaults = new JsonArray();
                LOG.info("PSA_MODEL_AUDIT START run={} count={}", run, ids.size());
            }
            if (ids == null) return;
            // Bound work per client tick. These are cached model lookups, not GPU render submissions.
            for (int limit = Math.min(position + 128, ids.size()); position < limit; position++) {
                var id = ids.get(position);
                var row = new JsonObject(); row.addProperty("id", id.toString());
                LOG.debug("PSA_MODEL_AUDIT LOOKUP run={} index={} id={}", run, position, id);
                try {
                    var item = ForgeRegistries.ITEMS.getValue(id);
                    var stack = item.getDefaultInstance();
                    if (stack.isEmpty() || stack.getItem() != item) {
                        row.addProperty("default_empty", stack.isEmpty());
                        row.addProperty("default_item", String.valueOf(ForgeRegistries.ITEMS.getKey(stack.getItem())));
                        defaults.add(row);
                        continue;
                    }
                    var model = mc.getItemRenderer().getModel(stack, null, null, 0);
                    if (model == null || model == mc.getModelManager().getMissingModel()) missing.add(row);
                    else real++;
                } catch (VirtualMachineError | ThreadDeath fatal) {
                    LOG.error("PSA_MODEL_AUDIT FATAL run={} index={} id={}", run, position, id, fatal);
                    throw fatal;
                } catch (Throwable failure) {
                    row.addProperty("exception_class", failure.getClass().getName()); errors.add(row);
                }
            }
            if (position != ids.size()) return;
            var report = new JsonObject();
            report.addProperty("run", run.toString()); report.addProperty("resource_generation", activeGeneration);
            report.addProperty("scope", "native default-stack ItemRenderer.getModel; null world/player; no render, texture, spawn, use or gameplay proof");
            report.addProperty("registered_nonvanilla_items", ids.size()); report.addProperty("processed", position);
            report.addProperty("nonmissing_model_lookups", real);
            report.addProperty("catalog_sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest((String.join("\n", ids.stream().map(ResourceLocation::toString).toList()) + "\n")
                    .getBytes(StandardCharsets.UTF_8))));
            report.add("missing_models", missing); report.add("lookup_errors", errors); report.add("default_stack_mismatches", defaults);
            var directory = FMLPaths.GAMEDIR.get().resolve("psa-model-audit");
            try {
                Files.createDirectories(directory);
                // One new, uniquely named report per resource bake; never replace a file being observed.
                Files.writeString(directory.resolve(run + ".json"), new GsonBuilder().setPrettyPrinting().create().toJson(report) + "\n",
                        StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
                LOG.info("PSA_MODEL_AUDIT COMPLETE run={} total={} nonmissing={} missing={} errors={} defaults={}",
                        run, position, real, missing.size(), errors.size(), defaults.size());
            } catch (IOException failure) {
                // Preserve a failed result and its item IDs in the log; never emit COMPLETE or retry every tick.
                LOG.error("PSA_MODEL_AUDIT FAILED report={}", report, failure);
            } finally {
                ids = null;
            }
        }
    }
}
