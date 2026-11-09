package dev.psa.menuidprobe;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import io.netty.buffer.Unpooled;
import java.nio.file.Files;
import net.minecraft.core.NonNullList;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.protocol.game.ClientboundContainerSetDataPacket;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.MenuProvider;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.ContainerData;
import net.minecraft.world.inventory.ContainerSynchronizer;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.common.capabilities.ForgeCapabilities;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/** Trusted local Java diagnostic; no script filter change, auth bypass or real client claim. */
@Mod("psamenuidprobe")
public final class MenuIdProbe {
    private static final boolean BASELINE = Boolean.getBoolean("psa.menu.baseline");
    private static final int WINDOW = 7;
    private int pendingTicks = -1;

    public MenuIdProbe() {
        MinecraftForge.EVENT_BUS.addListener(this::started);
        MinecraftForge.EVENT_BUS.addListener(this::tick);
    }

    private static final class Capture implements ContainerSynchronizer {
        int[] values;
        final java.util.List<int[]> changes = new java.util.ArrayList<>();
        @Override public void sendInitialData(AbstractContainerMenu menu, NonNullList<ItemStack> slots,
                ItemStack carried, int[] data) { values = data.clone(); }
        @Override public void sendSlotChange(AbstractContainerMenu menu, int slot, ItemStack stack) {}
        @Override public void sendCarriedChange(AbstractContainerMenu menu, ItemStack stack) {}
        @Override public void sendDataChange(AbstractContainerMenu menu, int index, int value) {
            changes.add(new int[] {index, value});
        }
    }

    private static Object field(Object object, String name) throws Exception {
        var reflected = object.getClass().getDeclaredField(name);
        reflected.setAccessible(true);
        return reflected.get(object);
    }

    private static MenuType<?> registered(String kind) throws Exception {
        var field = Class.forName("com.alc.moreminecarts.registry.MMContainers")
                .getField(kind.toUpperCase() + "_CART_CONTAINER");
        return (MenuType<?>) ((RegistryObject<?>) field.get(null)).get();
    }

    private static AbstractContainerMenu client(String kind, ServerLevel level, Player player) throws Exception {
        return (AbstractContainerMenu) Class.forName("com.alc.moreminecarts.containers."
                + (kind.equals("tank") ? "Tank" : "Battery") + "CartContainer")
                .getConstructor(int.class, Level.class, Inventory.class, Player.class)
                .newInstance(WINDOW, level, player.getInventory(), player);
    }

    private static Entity cart(String kind, ServerLevel level, int id, int amount) {
        Entity entity = ForgeRegistries.ENTITY_TYPES.getValue(new ResourceLocation("moreminecarts", kind + "_cart")).create(level);
        if (entity == null) throw new IllegalStateException("Cannot create cart " + kind);
        entity.setId(id);
        entity.setPos(0, -60, 0);
        if (kind.equals("tank")) {
            CompoundTag tag = entity.saveWithoutId(new CompoundTag());
            tag.putString("FluidName", "minecraft:water");
            tag.putInt("Amount", amount);
            entity.load(tag);
        } else {
            entity.getCapability(ForgeCapabilities.ENERGY).ifPresent(storage -> {
                for (int i = 0; i < amount; i++) storage.receiveEnergy(1000, false);
            });
        }
        return entity;
    }

    private static Object readValue(String kind, AbstractContainerMenu menu) throws Exception {
        return menu.getClass().getMethod(kind.equals("tank") ? "getFluids" : "getEnergy").invoke(menu);
    }

    private static int roundtrip(int index, int value) {
        FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
        try {
            new ClientboundContainerSetDataPacket(WINDOW, index, value).write(buffer);
            ClientboundContainerSetDataPacket decoded = new ClientboundContainerSetDataPacket(buffer);
            if (decoded.getContainerId() != WINDOW || decoded.getId() != index || buffer.readableBytes() != 0)
                throw new IllegalStateException("Packet envelope differs");
            return decoded.getValue();
        } finally { buffer.release(); }
    }

    private static int[] serverData(Entity entity, Player player) {
        AbstractContainerMenu menu = ((MenuProvider) entity).createMenu(WINDOW, player.getInventory(), player);
        if (menu == null) throw new IllegalStateException("No server menu");
        Capture capture = new Capture();
        menu.setSynchronizer(capture);
        if (capture.values == null) throw new IllegalStateException("No initial data callback");
        return capture.values;
    }

    private static JsonObject boundary(String kind, ServerLevel level, Player player, int source) throws Exception {
        Entity entity = cart(kind, level, source, kind.equals("tank") ? 1000 : 1);
        AbstractContainerMenu menu = client(kind, level, player);
        try {
            int[] values = serverData(entity, player);
            for (int i = 0; i < values.length; i++) menu.setData(i, roundtrip(i, values[i]));
            int actual = ((ContainerData) field(menu, "data")).get(0);
            boolean type = menu.getType() == registered(kind);
            int expected = BASELINE ? (short) source : source;
            if (actual != expected || type != (!BASELINE || kind.equals("tank")))
                throw new IllegalStateException("Unexpected boundary/type result: " + kind + "/" + source + "/" + actual + "/" + type);
            if (values.length != (BASELINE ? 1 : 2)) throw new IllegalStateException("Unexpected wire property count");
            JsonObject row = new JsonObject();
            row.addProperty("kind", kind); row.addProperty("source_id", source); row.addProperty("decoded_logical_id", actual);
            row.addProperty("wire_properties", values.length); row.addProperty("menu_type_correct", type);
            row.addProperty("full_id_preserved", actual == source);
            return row;
        } finally { entity.discard(); }
    }

    private static JsonObject partialAlias(String kind, ServerLevel level, Player player) throws Exception {
        int source = 251992;
        int alias = (short) source;
        if (level.getEntity(source) != null || level.getEntity(alias) != null)
            throw new IllegalStateException("QA entity ID already occupied");
        Entity wanted = cart(kind, level, source, kind.equals("tank") ? 2000 : 2);
        Entity decoy = cart(kind, level, alias, kind.equals("tank") ? 1000 : 1);
        try {
            var spawn = level.getSharedSpawnPos();
            wanted.setPos(spawn.getX() + 0.5, spawn.getY(), spawn.getZ() + 0.5);
            decoy.setPos(spawn.getX() + 0.5, spawn.getY(), spawn.getZ() + 0.5);
            if (!level.addFreshEntity(wanted) || !level.addFreshEntity(decoy)) throw new IllegalStateException("Cannot add owned QA carts");
            if (level.getEntity(source) != wanted || level.getEntity(alias) != decoy)
                throw new IllegalStateException("Owned QA chunk is not entity-accessible");
            AbstractContainerMenu menu = client(kind, level, player);
            int[] values = serverData(wanted, player);
            menu.setData(0, roundtrip(0, values[0]));
            readValue(kind, menu); // A rendered frame could ask before the second half arrives.
            Object afterFirst = field(menu, "entity");
            if (afterFirst != (BASELINE ? decoy : null)) throw new IllegalStateException("Initial partial ID was exposed or baseline alias not reproduced");
            for (int i = 1; i < values.length; i++) menu.setData(i, roundtrip(i, values[i]));
            Object value = readValue(kind, menu);
            Object actual = field(menu, "entity");
            if (actual != (BASELINE ? decoy : wanted)) throw new IllegalStateException("Wrong cart after complete data");
            JsonObject row = new JsonObject();
            row.addProperty("kind", kind); row.addProperty("source_id", source); row.addProperty("alias_id", alias);
            row.addProperty("first_half_cached_decoy", afterFirst == decoy);
            row.addProperty("complete_data_resolved_wanted", actual == wanted);
            row.addProperty("getter_returned_nonnull", value != null);
            return row;
        } finally { wanted.discard(); decoy.discard(); }
    }

    @SuppressWarnings("unchecked")
    private static JsonObject completionCounter(ServerLevel level, Player player, int source) throws Exception {
        Class<?> boardClass = Class.forName("io.ejekta.bountiful.content.board.BoardBlockEntity");
        var block = ForgeRegistries.BLOCKS.getValue(new ResourceLocation("bountiful", "bountyboard"));
        if (block == null) throw new IllegalStateException("Missing pinned bounty board");
        var board = (net.minecraft.world.level.block.entity.BlockEntity) boardClass
                .getConstructor(net.minecraft.core.BlockPos.class, net.minecraft.world.level.block.state.BlockState.class)
                .newInstance(level.getSharedSpawnPos(), block.defaultBlockState());
        board.setLevel(level);
        var counts = (java.util.Map<String, Integer>) field(board, "finishMap");
        counts.clear(); counts.put("owned-local-qa-counter", source);
        AbstractContainerMenu server = ((MenuProvider) board).createMenu(WINDOW, player.getInventory(), player);
        AbstractContainerMenu client = (AbstractContainerMenu) Class.forName("io.ejekta.bountiful.content.gui.BoardScreenHandler")
                .getConstructor(int.class, Inventory.class).newInstance(WINDOW, player.getInventory());
        Capture capture = new Capture(); server.setSynchronizer(capture);
        if (capture.values == null || capture.values.length != (BASELINE ? 1 : 2))
            throw new IllegalStateException("Unexpected completion counter properties");
        for (int i = 0; i < capture.values.length; i++) client.setData(i, roundtrip(i, capture.values[i]));
        int actual = (Integer) client.getClass().getMethod("getTotalNumComplete").invoke(client);
        if (actual != (BASELINE ? (short) source : source))
            throw new IllegalStateException("Wrong completion counter: " + source + "/" + actual);
        JsonObject row = new JsonObject(); row.addProperty("source_count", source);
        row.addProperty("decoded_count", actual); row.addProperty("full_count_preserved", actual == source);
        if (source == 65535) {
            JsonArray updates = new JsonArray();
            for (int next : new int[] {65536, 65537, 131071, 131072, 0}) {
                counts.put("owned-local-qa-counter", next);
                capture.changes.clear();
                server.broadcastChanges();
                if (capture.changes.isEmpty()) throw new IllegalStateException("No counter update packets");
                for (int[] change : capture.changes) client.setData(change[0], roundtrip(change[0], change[1]));
                int updated = (Integer) client.getClass().getMethod("getTotalNumComplete").invoke(client);
                if (updated != (BASELINE ? (short) next : next))
                    throw new IllegalStateException("Wrong broadcast completion update");
                JsonObject update = new JsonObject(); update.addProperty("source_count", next);
                update.addProperty("decoded_count", updated); update.addProperty("packets", capture.changes.size());
                updates.add(update);
            }
            row.add("broadcast_updates", updates);
        }
        return row;
    }

    private void started(ServerStartedEvent event) {
        var level = event.getServer().overworld();
        var spawn = level.getSharedSpawnPos();
        // Full packs can defer spawn-chunk entity visibility until their first ticks.
        level.setChunkForced(spawn.getX() >> 4, spawn.getZ() >> 4, true);
        pendingTicks = 40;
    }

    private void tick(TickEvent.ServerTickEvent event) {
        if (event.phase != TickEvent.Phase.END || pendingTicks < 0 || --pendingTicks != 0) return;
        pendingTicks = -1;
        try {
            ServerLevel level = event.getServer().overworld();
            Player player = FakePlayerFactory.getMinecraft(level);
            JsonArray boundaries = new JsonArray();
            for (String kind : new String[] {"tank", "battery"})
                for (int id : new int[] {0, 32767, 32768, 65535, 65536, 251992, Integer.MAX_VALUE, Integer.MIN_VALUE})
                    boundaries.add(boundary(kind, level, player, id));
            JsonArray aliases = new JsonArray();
            for (String kind : new String[] {"tank", "battery"}) aliases.add(partialAlias(kind, level, player));
            JsonArray counters = new JsonArray();
            if (ModList.get().isLoaded("bountiful"))
                for (int count : new int[] {0, 32767, 32768, 65535, 65536, 251992, Integer.MAX_VALUE, Integer.MIN_VALUE})
                    counters.add(completionCounter(level, player, count));
            JsonObject report = new JsonObject(); report.addProperty("baseline", BASELINE);
            report.addProperty("scope", "real server and client-constructor menu logic with actual vanilla packet roundtrip on dedicated level; not authenticated client rendering");
            report.add("boundaries", boundaries); report.add("partial_aliases", aliases);
            report.add("completion_counter_boundaries", counters);
            var directory = FMLPaths.GAMEDIR.get().resolve("psa-validation"); Files.createDirectories(directory);
            Files.writeString(directory.resolve("menu-id-wire.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report) + "\n");
            System.out.println("PSA_MENU_ID_PROBE " + (BASELINE ? "BASELINE_REPRODUCED" : "PATCHED_PASS") + " boundaries=" + boundaries.size() + " alias_cases=" + aliases.size() + " counters=" + counters.size());
        } catch (Throwable failure) {
            System.err.println("PSA_MENU_ID_PROBE FAILED"); failure.printStackTrace();
        } finally { event.getServer().halt(false); }
    }
}
