package dev.psa.renderprobe;

import com.google.gson.JsonObject;
import java.util.HashSet;
import java.util.Set;
import java.util.ArrayDeque;
import java.util.TreeSet;
import java.util.concurrent.ArrayBlockingQueue;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.registries.ForgeRegistries;
import static dev.psa.renderprobe.RenderProtocol.*;

/** Client-only observer: never renders an item itself or catches game renderer failures. */
@Mod.EventBusSubscriber(modid = "psarenderprobe", value = Dist.CLIENT)
public final class RenderClient {
    private static volatile Batch batch;
    private static final Set<Integer> begun = new HashSet<>(), returned = new HashSet<>();
    private static final ArrayDeque<Integer> rendering = new ArrayDeque<>();
    private static int modelObservedMask, missingMask;
    private static int fallbackPartialMask, visualPartialMask, modelWaitTicks;
    private static volatile boolean sent;
    private static final Set<String> partialModelItems = new TreeSet<>();
    private static final ArrayBlockingQueue<VisualFrame> visualFrames = new ArrayBlockingQueue<>(128);
    private record VisualFrame(Batch batch, Entity entity, BakedModel model, boolean nativeModelPresent) {}
    private RenderClient() {}
    public static void accept(Batch value) {
        if (batch == null || !batch.run().equals(value.run())) partialModelItems.clear();
        batch = value; begun.clear(); returned.clear(); rendering.clear(); modelObservedMask = 0; missingMask = 0; sent = false;
        fallbackPartialMask = 0; visualPartialMask = 0; modelWaitTicks = 0;
        persist("awaiting_native_render");
    }
    private static int find(Entity entity) {
        if (batch == null || sent) return -1;
        for (int i = 0; i < batch.tokens().size(); i++) {
            Token token = batch.tokens().get(i);
            if (entity.getId() == token.entityId() && entity.getUUID().equals(token.entityUuid())
                    && token.entityClass().equals(entity.getClass().getName())
                    && token.entityType().equals(String.valueOf(ForgeRegistries.ENTITY_TYPES.getKey(entity.getType())))
                    && token.itemId().equals(String.valueOf(ForgeRegistries.ITEMS.getKey(DropStackView.stack(entity).getItem())))) return i;
        }
        return -1;
    }
    public static void before(Entity entity) {
        int current = find(entity);
        rendering.push(current);
        if (current >= 0 && begun.add(current)) {
            System.out.println("PSA_RENDER BEGIN " + batch.tokens().get(current));
            persist("native_render_entered");
        }
    }
    public static void after(Entity entity) {
        int index = rendering.pop();
        if (index != find(entity)) throw new IllegalStateException("Entity identity changed during rendering");
        if (index >= 0) {
            if (!begun.contains(index)) throw new IllegalStateException("Renderer RETURN without observed HEAD");
            if (returned.add(index)) {
                System.out.println("PSA_RENDER RETURN " + batch.tokens().get(index));
                persist("native_render_returned");
            }
        }
    }
    public static void model(ItemStack stack, BakedModel model) {
        if (batch == null || sent || rendering.isEmpty() || rendering.peek() < 0) return;
        int current = rendering.peek();
        Token token = batch.tokens().get(current);
        if (!token.itemId().equals(String.valueOf(ForgeRegistries.ITEMS.getKey(stack.getItem())))) return;
        observeModel(current, model, true);
    }
    private static void observeModel(int current, BakedModel model, boolean nativeModelPresent) {
        modelObservedMask |= 1 << current;
        if (!nativeModelPresent || model == null || model == Minecraft.getInstance().getModelManager().getMissingModel())
            missingMask |= 1 << current;
    }
    /** Called only after Create's original cached partial-buffer call returns. */
    public static void packageFallback(Entity entity, BakedModel model) {
        if (batch == null || sent || rendering.isEmpty()) return;
        int current = rendering.peek();
        if (current < 0 || current != find(entity)) return;
        fallbackPartialMask |= 1 << current;
        observeModel(current, model, true);
        if ((missingMask & 1 << current) == 0) partialModelItems.add(batch.tokens().get(current).itemId());
    }
    /** Flywheel may run frames on workers. Only enqueue; client state is updated by client tick. */
    public static void packageVisualFrame(Entity entity, BakedModel model, boolean nativeModelPresent) {
        Batch current = batch;
        if (current == null || sent) return;
        for (Token token : current.tokens()) {
            if (token.entityId() == entity.getId() && token.entityUuid().equals(entity.getUUID())) {
                // A full queue drops evidence and may fail verification; never block or fabricate it.
                visualFrames.offer(new VisualFrame(current, entity, model, nativeModelPresent));
                return;
            }
        }
    }
    private static void consumeVisualFrames() {
        VisualFrame frame;
        while ((frame = visualFrames.poll()) != null) {
            // The immutable packet instance must still be current, even if metadata is reused.
            if (batch == null || sent || frame.batch() != batch) continue;
            int current = find(frame.entity());
            if (current < 0) continue;
            visualPartialMask |= 1 << current;
            observeModel(current, frame.model(), frame.nativeModelPresent());
            if ((missingMask & 1 << current) == 0) partialModelItems.add(batch.tokens().get(current).itemId());
        }
    }
    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) return;
        consumeVisualFrames();
        if (batch == null || sent || returned.size() != batch.tokens().size()) return;
        // Native Flywheel frames can complete asynchronously after the entity renderer returns.
        if (missingMask == 0 && modelObservedMask != (1 << batch.tokens().size()) - 1 && ++modelWaitTicks < 20) {
            persist("awaiting_native_model_path");
            return;
        }
        sent = true;
        persist(missingMask != 0 ? "ack_missing_model" : modelObservedMask != (1 << batch.tokens().size()) - 1
                ? "ack_render_return_model_unobserved" : "ack_all_native_returns_and_models");
        RenderNetwork.CHANNEL.sendToServer(new Ack(batch, modelObservedMask, missingMask));
    }
    @SubscribeEvent
    public static void logout(ClientPlayerNetworkEvent.LoggingOut event) {
        if (batch != null && !sent) persist("disconnected_before_all_returns");
        batch = null; begun.clear(); returned.clear(); rendering.clear(); sent = false;
        visualFrames.clear(); partialModelItems.clear();
    }
    private static void persist(String status) {
        JsonObject value = new JsonObject();
        value.addProperty("run", batch.run().toString()); value.addProperty("batch", batch.index());
        value.addProperty("status", status); value.addProperty("begun_count", begun.size());
        value.addProperty("native_return_count", returned.size()); value.addProperty("missing_model_mask", missingMask);
        value.addProperty("model_observed_mask", modelObservedMask);
        value.addProperty("fallback_partial_model_mask", fallbackPartialMask);
        value.addProperty("visual_partial_model_mask", visualPartialMask);
        value.add("native_partial_model_items", new com.google.gson.Gson().toJsonTree(partialModelItems));
        value.add("tokens", new com.google.gson.Gson().toJsonTree(batch.tokens()));
        RenderProbe.write(FMLPaths.GAMEDIR.get().resolve("psa-validation/render-client-current.json"), value);
    }
}
