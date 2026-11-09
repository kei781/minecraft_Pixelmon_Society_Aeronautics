package dev.psa.renderprobe;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.UUID;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.network.PacketDistributor;
import net.minecraftforge.registries.ForgeRegistries;
import static dev.psa.renderprobe.RenderProtocol.*;

/** Normal native spawn/network/render probe. No automatic world mutation at startup. */
@Mod("psarenderprobe")
public final class RenderProbe {
    private static Session session;
    private static final Path ROOT = FMLPaths.GAMEDIR.get();
    private static final com.google.gson.Gson JSON = new GsonBuilder().create();
    public RenderProbe() {
        RenderNetwork.register();
        MinecraftForge.EVENT_BUS.addListener(this::commands);
        MinecraftForge.EVENT_BUS.addListener(this::tick);
        MinecraftForge.EVENT_BUS.addListener(this::stopping);
        MinecraftForge.EVENT_BUS.addListener(EventPriority.LOWEST, this::joined);
    }
    private static boolean enabled() {
        return Boolean.getBoolean("psa.render.enabled") && Files.isRegularFile(ROOT.resolve(".psa-disposable-qa"));
    }
    private void commands(RegisterCommandsEvent event) {
        event.getDispatcher().register(Commands.literal("psa_render")
                .requires(source -> source.getEntity() == null && source.hasPermission(4))
                .then(Commands.literal("status").executes(context -> {
                    context.getSource().sendSuccess(() -> Component.literal(session == null ? "PSA_RENDER idle" : session.status().toString()), false);
                    return 1;
                }))
                .then(Commands.literal("stop").executes(context -> {
                    if (session != null && session.active) session.stop("controller_stop"); return 1;
                }))
                .then(Commands.literal("native").then(Commands.argument("start", IntegerArgumentType.integer(0))
                    .then(Commands.argument("count", IntegerArgumentType.integer(1, 20000)).executes(context -> {
                        if (!enabled()) throw new IllegalStateException("Disposable marker and explicit render opt-in required");
                        if (session != null && session.active) throw new IllegalStateException("Render run already active");
                        List<ResourceLocation> catalog = catalog();
                        int start = IntegerArgumentType.getInteger(context, "start"), count = IntegerArgumentType.getInteger(context, "count");
                        if (start >= catalog.size()) throw new IllegalArgumentException("Catalog start outside range");
                        session = new Session(context.getSource().getServer().overworld(),
                                catalog.subList(start, Math.min(catalog.size(), start + count)), start, catalog.size());
                        session.checkpoint(); return 1;
                    }))))
                .then(Commands.literal("start").then(Commands.argument("player", EntityArgument.player())
                    .then(Commands.argument("start", IntegerArgumentType.integer(0))
                    .then(Commands.argument("count", IntegerArgumentType.integer(1, 20000)).executes(context -> {
                        if (!enabled()) throw new IllegalStateException("Disposable marker and explicit render opt-in required");
                        if (session != null && session.active) throw new IllegalStateException("Render run already active");
                        ServerPlayer player = EntityArgument.getPlayer(context, "player");
                        List<ResourceLocation> catalog = catalog();
                        int start = IntegerArgumentType.getInteger(context, "start"), count = IntegerArgumentType.getInteger(context, "count");
                        if (start >= catalog.size()) throw new IllegalArgumentException("Catalog start outside range");
                        session = new Session(player, catalog.subList(start, Math.min(catalog.size(), start + count)), start, catalog.size());
                        session.checkpoint();
                        return 1;
                    }))))));
    }
    private static List<ResourceLocation> catalog() {
        return ForgeRegistries.ITEMS.getKeys().stream().filter(id -> !id.getNamespace().equals("minecraft"))
                .sorted(java.util.Comparator.comparing(ResourceLocation::toString)).toList();
    }
    private void joined(EntityJoinLevelEvent event) {
        if (session == null || !session.active || session.cleaning || session.expected != null || event.isCanceled()
                || event.getLevel() != session.level || !(event.getEntity() instanceof ItemEntity item)) return;
        ResourceLocation id = ForgeRegistries.ITEMS.getKey(item.getItem().getItem());
        Spawn row = session.spawning.get(id);
        if (row == null || row.position.distanceToSqr(item.position()) > 0.25) return;
        if (row.entity != null && row.entity != item) {
            session.stop("ambiguous_native_item_entity:" + id); return;
        }
        row.entity = item;
        session.owned.put(item.getUUID(), item);
        freeze(item);
    }
    private void tick(TickEvent.ServerTickEvent event) {
        if (event.phase != TickEvent.Phase.END || session == null || !session.active) return;
        try { session.tick(); }
        catch (Exception failure) { session.stop("probe_exception:" + failure); failure.printStackTrace(); }
    }
    private void stopping(ServerStoppingEvent event) {
        if (session != null && session.active && session.level.getServer() == event.getServer()) session.stop("server_stopping");
    }
    public static void acknowledge(ServerPlayer sender, Ack message) {
        if (session == null || !session.active || sender == null || sender.serverLevel() != session.level
                || !matches(sender.getUUID(), session.playerId, session.expected, message)) {
            System.err.println("PSA_RENDER rejected stale/wrong-identity acknowledgement"); return;
        }
        if (message.missingModelMask() != 0) {
            session.stop("missing_model_mask:" + message.missingModelMask()); return;
        }
        JsonObject row = new JsonObject();
        row.addProperty("run", session.run.toString()); row.addProperty("batch", session.batch);
        row.add("render_return_tokens", JSON.toJsonTree(session.expected.tokens()));
        append(session.journal, row);
        session.completed += session.expected.tokens().size();
        session.cleanup(); session.expected = null; session.spawning.clear(); session.batch++; session.age = 0;
        session.checkpoint();
    }
    private static void freeze(ItemEntity item) {
        item.setNoGravity(true); item.setDeltaMovement(Vec3.ZERO); item.setPickUpDelay(32767); item.setUnlimitedLifetime();
    }
    public static void write(Path destination, JsonObject value) {
        try {
            Files.createDirectories(destination.getParent());
            Files.writeString(destination, JSON.toJson(value) + "\n");
        } catch (Exception failure) { throw new IllegalStateException("Cannot persist render checkpoint", failure); }
    }
    private static void append(Path destination, JsonObject value) {
        try {
            Files.createDirectories(destination.getParent());
            Files.writeString(destination, JSON.toJson(value) + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Exception failure) { throw new IllegalStateException("Cannot persist render journal", failure); }
    }
    private static final class Spawn {
        final ResourceLocation item; final Vec3 position; ItemEntity entity;
        Spawn(ResourceLocation item, Vec3 position) { this.item = item; this.position = position; }
    }
    private static final class Session {
        final UUID run = UUID.randomUUID(), playerId;
        final ServerLevel level;
        final List<ResourceLocation> catalog;
        final LinkedHashMap<UUID, ItemEntity> owned = new LinkedHashMap<>();
        final LinkedHashMap<ResourceLocation, Spawn> spawning = new LinkedHashMap<>();
        final Path journal = ROOT.resolve("psa-validation/render-" + run + ".jsonl");
        final int catalogStart, totalCatalog;
        final Vec3 anchor;
        int completed, nativeSpawned, cursor, batch, age;
        boolean active = true;
        boolean cleaning;
        final java.util.Set<ChunkPos> ownedChunkTickets = new java.util.LinkedHashSet<>();
        String result = "running";
        String lastOperation = "created";
        Batch expected;
        Session(ServerPlayer player, List<ResourceLocation> catalog, int catalogStart, int totalCatalog) {
            this.playerId = player.getUUID(); this.level = player.serverLevel(); this.catalog = List.copyOf(catalog);
            this.catalogStart = catalogStart; this.totalCatalog = totalCatalog; this.anchor = player.position();
            player.teleportTo(level, anchor.x, anchor.y, anchor.z, 0, 12);
            prepareTickets();
        }
        Session(ServerLevel level, List<ResourceLocation> catalog, int catalogStart, int totalCatalog) {
            this.playerId = null; this.level = level; this.catalog = List.copyOf(catalog);
            this.catalogStart = catalogStart; this.totalCatalog = totalCatalog;
            this.anchor = new Vec3(8, level.getMinBuildHeight() + 5, 8);
            // Explicit native-only control: no player or client acknowledgement is fabricated.
            prepareTickets();
        }
        Vec3 fixturePosition(int index) { return anchor.add((index - 1.5) * 0.6, 1.0, 3.0); }
        void prepareTickets() {
            for (int i = 0; i < 4; i++) {
                ChunkPos chunk = new ChunkPos(BlockPos.containing(fixturePosition(i)));
                if (!level.getForcedChunks().contains(chunk.toLong())) {
                    ownedChunkTickets.add(chunk);
                    checkpoint(); // identify owned tickets before starting chunk work
                    level.setChunkForced(chunk.x, chunk.z, true);
                }
            }
        }
        void tick() {
            ServerPlayer player = playerId == null ? null : level.getServer().getPlayerList().getPlayer(playerId);
            if (playerId != null && (player == null || player.serverLevel() != level)) { stop("player_disconnected_or_changed_dimension"); return; }
            if (player != null && player.position().distanceToSqr(anchor) > 1) { stop("camera_player_moved"); return; }
            if (++age > 400) {
                stop(spawning.isEmpty() && cursor == 0 ? "fixture_chunk_activation_timeout"
                        : expected == null ? "spawn_timeout_or_unsupported_custom_entity" : "render_ack_timeout"); return;
            }
            for (int i = 0; i < 4; i++)
                if (!level.isPositionEntityTicking(BlockPos.containing(fixturePosition(i)))) return;
            if (expected != null) return;
            if (spawning.isEmpty()) {
                if (cursor == catalog.size()) { stop("complete"); return; }
                for (int i = 0; i < 4 && cursor < catalog.size(); i++) {
                    ResourceLocation id = catalog.get(cursor++);
                    Vec3 position = fixturePosition(i);
                    spawning.put(id, new Spawn(id, position));
                }
                checkpoint(); // persist the attempted IDs BEFORE calling mod item code
                for (Spawn row : List.copyOf(spawning.values())) {
                    lastOperation = "default_stack_and_spawn:" + row.item; checkpoint();
                    ItemStack stack = ForgeRegistries.ITEMS.getValue(row.item).getDefaultInstance();
                    if (stack.isEmpty()) { stop("empty_default_stack:" + row.item); return; }
                    if (!row.item.equals(ForgeRegistries.ITEMS.getKey(stack.getItem()))) {
                        stop("default_stack_registry_identity_changed:" + row.item); return;
                    }
                    ItemEntity item = new ItemEntity(level, row.position.x, row.position.y, row.position.z, stack);
                    freeze(item);
                    // Forge's native join handler may cancel this and enqueue a custom ItemEntity.
                    level.addFreshEntity(item);
                    if (!active) return;
                }
                return;
            }
            if (spawning.values().stream().anyMatch(row -> row.entity == null)) return;
            List<Token> tokens = new ArrayList<>();
            for (Spawn row : spawning.values()) {
                if (level.getEntity(row.entity.getUUID()) != row.entity || !row.entity.isAlive()) return;
                freeze(row.entity);
                tokens.add(new Token(row.entity.getId(), row.entity.getUUID(), row.item.toString()));
            }
            nativeSpawned += tokens.size();
            if (playerId == null) {
                JsonObject row = new JsonObject(); row.addProperty("run", run.toString()); row.addProperty("batch", batch);
                row.add("native_spawn_tokens", JSON.toJsonTree(tokens));
                append(journal, row);
                cleanup(); spawning.clear(); batch++; age = 0; checkpoint();
                return;
            }
            expected = new Batch(run, batch, tokens); age = 0;
            RenderNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player), expected);
            checkpoint();
        }
        void cleanup() {
            cleaning = true;
            try {
                // These exact references were captured from our native spawn events.
                // UUID lookup can be hidden after a chunk unload or player disconnect.
                for (ItemEntity entity : List.copyOf(owned.values())) entity.discard();
            } finally {
                owned.clear(); cleaning = false;
            }
        }
        void stop(String why) {
            result = why; active = false;
            try { checkpoint(); } finally {
                try { cleanup(); } finally {
                    for (ChunkPos chunk : ownedChunkTickets) level.setChunkForced(chunk.x, chunk.z, false);
                    ownedChunkTickets.clear();
                }
            }
            checkpoint();
            System.out.println("PSA_RENDER STOP " + status());
        }
        JsonObject status() {
            JsonObject value = new JsonObject();
            value.addProperty("run", run.toString()); value.addProperty("result", result);
            value.addProperty("catalog_total", totalCatalog); value.addProperty("catalog_start", catalogStart);
            value.addProperty("selected_count", catalog.size()); value.addProperty("completed_render_returns", completed);
            value.addProperty("completed_native_spawns", nativeSpawned);
            value.addProperty("mode", playerId == null ? "native_server_spawn_only" : "authenticated_client_render");
            value.addProperty("batch", batch); value.addProperty("active", active);
            value.addProperty("last_operation", lastOperation);
            value.addProperty("owned_fixture_chunk_ticket_count", ownedChunkTickets.size());
            JsonArray attempted = new JsonArray(); for (var row : spawning.values()) attempted.add(row.item.toString());
            value.add("attempted_ids", attempted);
            value.addProperty("scope", playerId == null ? "native server item spawning only; no client/render attempt"
                    : "native default item entity spawn/network/render RETURN only; not texture, placement or functional-use proof");
            return value;
        }
        void checkpoint() {
            write(ROOT.resolve("psa-validation/render-server-current.json"), status());
            write(ROOT.resolve("psa-validation/render-" + run + "-summary.json"), status());
        }
    }
}
