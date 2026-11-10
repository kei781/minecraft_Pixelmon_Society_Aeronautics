package dev.psa.probe;

import com.google.gson.JsonParser;
import com.mojang.logging.LogUtils;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.core.Direction;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.RandomSource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ModelEvent;
import net.minecraftforge.client.model.data.ModelData;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.slf4j.Logger;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;

/** Diagnostic only: registered/baked models, never authenticated gameplay evidence. */
@Mod("psamodelprobe")
public final class ModelProbe {
    @Mod.EventBusSubscriber(modid = "psamodelprobe", value = Dist.CLIENT, bus = Mod.EventBusSubscriber.Bus.MOD)
    public static final class Client {
        private static final Logger LOG = LogUtils.getLogger();
        private static final List<ResourceLocation> TARGETS;
        static {
            try (var input = ModelProbe.class.getResourceAsStream("/psa-model-probe-targets.txt")) {
                if (input == null) throw new IllegalStateException("Missing model targets");
                TARGETS = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))
                        .lines().filter(line -> !line.isBlank()).map(ResourceLocation::new).toList();
                if (TARGETS.size() != 17) throw new IllegalStateException("Unexpected model targets");
            } catch (Exception failure) {
                throw new IllegalStateException("PSA model probe targets", failure);
            }
        }

        @SubscribeEvent
        public static void register(ModelEvent.RegisterAdditional event) {
            TARGETS.forEach(event::register);
        }

        @SubscribeEvent
        public static void baked(ModelEvent.BakingCompleted event) {
            int passed = 0;
            var resources = Minecraft.getInstance().getResourceManager();
            var missingGeometry = geometry(event.getModelManager().getMissingModel());
            boolean selected = resources.listPacks().anyMatch(pack -> pack.packId().equals("file/PSA-Forge-Model-Compat.zip"));
            for (var target : TARGETS) {
                BakedModel model = event.getModels().get(target);
                boolean real = model != null && model != event.getModelManager().getMissingModel();
                int quads = 0;
                boolean missing = true;
                String loader = "unreadable";
                try (var reader = resources.getResource(new ResourceLocation(target.getNamespace(),
                        "models/" + target.getPath() + ".json")).orElseThrow().openAsReader()) {
                    loader = JsonParser.parseReader(reader).getAsJsonObject().get("loader").getAsString();
                    if (real) {
                        var actualGeometry = geometry(model);
                        quads = actualGeometry.size();
                        missing = actualGeometry.equals(missingGeometry);
                    }
                } catch (Exception failure) {
                    LOG.error("PSA_MODEL_PROBE read/bake failed {}", target, failure);
                }
                boolean ok = real && quads > 0 && !missing && loader.equals("forge:obj");
                if (ok) passed++;
                LOG.info("PSA_MODEL_PROBE model={} loader={} real={} quads={} missing_geometry={} passed={}", target, loader, real, quads, missing, ok);
            }
            LOG.info("PSA_MODEL_PROBE SUMMARY passed={} total={} compatibility_pack_selected={}", passed, TARGETS.size(), selected);
        }

        private static List<String> geometry(BakedModel model) {
            List<BakedQuad> quads = new ArrayList<>(model.getQuads(null, null,
                    RandomSource.create(0), ModelData.EMPTY, null));
            for (var side : Direction.values())
                quads.addAll(model.getQuads(null, side, RandomSource.create(0), ModelData.EMPTY, null));
            List<String> signatures = new ArrayList<>();
            for (var quad : quads)
                signatures.add(Arrays.toString(quad.getVertices()) + ":" + quad.getSprite().contents().name()
                        + ":" + quad.getTintIndex() + ":" + quad.getDirection() + ":" + quad.isShade());
            Collections.sort(signatures);
            return signatures;
        }
    }
}
