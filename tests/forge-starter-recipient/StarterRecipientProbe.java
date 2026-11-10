package dev.psa.starterprobe;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.pixelmonmod.pixelmon.TickHandler;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.minecraft.commands.Commands;
import net.minecraft.server.MinecraftServer;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.fml.common.Mod;

/** Explicit synthetic offline UUID inputs; never creates or authenticates a player. */
@Mod("psastarterprobe")
public final class StarterRecipientProbe {
    private static Set<UUID> pending;
    private final String run = UUID.randomUUID().toString();
    private final List<UUID> owned = List.of(UUID.randomUUID(), UUID.randomUUID());
    private MinecraftServer server;
    private int startTick, checkpoint, lastElapsed;
    private boolean started, finished;

    @SuppressWarnings("unchecked")
    public StarterRecipientProbe() throws Exception {
        Path root = Path.of("").toAbsolutePath();
        if (!Boolean.getBoolean("psa.starterProbe") || !Files.readString(root.resolve(".psa-starter-probe"))
                .equals("psa-disposable-starter-probe-v1\n")) throw new IllegalStateException("Owned disposable starter probe required");
        Path pixelmon = root.resolve("mods/Pixelmon-1.20.1-9.2.3-universal.jar");
        if (Files.isSymbolicLink(pixelmon)) throw new IllegalStateException("Regular pinned Pixelmon required");
        var hash = MessageDigest.getInstance("SHA-256");
        try (var input = Files.newInputStream(pixelmon)) {
            byte[] buffer = new byte[65536]; int count;
            while ((count = input.read(buffer)) != -1) hash.update(buffer, 0, count);
        }
        if (!HexFormat.of().formatHex(hash.digest()).equals("8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a"))
            throw new IllegalStateException("Pinned native binary differs");
        Field field = TickHandler.class.getDeclaredField("playerListForStartMenu");
        field.setAccessible(true); pending = (Set<UUID>) field.get(null);
        if (pending == null) throw new IllegalStateException("Native pending set required");
        MinecraftForge.EVENT_BUS.addListener(this::commands);
        MinecraftForge.EVENT_BUS.addListener(EventPriority.LOWEST, this::tick);
        MinecraftForge.EVENT_BUS.addListener(this::stopping);
    }

    private void commands(RegisterCommandsEvent event) {
        event.getDispatcher().register(Commands.literal("psa_starter_probe_start")
            .requires(source -> source.getEntity() == null && source.hasPermission(4))
            .executes(context -> {
                server = context.getSource().getServer();
                if (!server.isDedicatedServer() || server.getPlayerCount() != 0 || started || !pending.isEmpty())
                    throw new IllegalStateException("Fresh dedicated zero-player empty-queue profile required");
                for (UUID id : owned) if (server.getPlayerList().getPlayer(id) != null)
                    throw new IllegalStateException("Synthetic UUID unexpectedly online");
                started = true; startTick = server.getTickCount();
                pending.addAll(owned); write("armed", false, false); return 1;
            }));
        event.getDispatcher().register(Commands.literal("psa_starter_queue_status")
            .requires(source -> source.getEntity() == null && source.hasPermission(4))
            .executes(context -> {
                var active = context.getSource().getServer();
                if (!active.isDedicatedServer()) throw new IllegalStateException("Dedicated probe only");
                long online = pending.stream().filter(id -> active.getPlayerList().getPlayer(id) != null).count();
                var status = new JsonObject(); status.addProperty("pending", pending.size());
                status.addProperty("online_pending", online); status.addProperty("offline_pending", pending.size() - online);
                status.addProperty("actual_online_players", active.getPlayerCount());
                status.addProperty("server_tick", active.getTickCount());
                save("status", status); return 1;
            }));
        event.getDispatcher().register(Commands.literal("psa_starter_probe_online_arm")
            .requires(source -> source.getEntity() == null && source.hasPermission(4))
            .executes(context -> {
                var active = context.getSource().getServer();
                if (!active.isDedicatedServer() || active.getPlayerCount() != 1 || !pending.isEmpty())
                    throw new IllegalStateException("One genuine online player and empty queue required");
                // Calls the native API on the real authenticated ServerPlayer. No identity is manufactured.
                TickHandler.registerStarterList(active.getPlayerList().getPlayers().get(0));
                var result = new JsonObject(); result.addProperty("actual_online_players", active.getPlayerCount());
                result.addProperty("pending", pending.size()); result.addProperty("server_tick", active.getTickCount());
                save("genuine_online_armed", result); return 1;
            }));
    }

    private void tick(TickEvent.ServerTickEvent event) {
        if (event.phase != TickEvent.Phase.END || !started || finished) return;
        lastElapsed = server.getTickCount() - startTick;
        if (lastElapsed < 220) return;
        boolean pruned = owned.stream().noneMatch(pending::contains);
        boolean pass = pruned && pending.isEmpty() && server.getPlayerCount() == 0;
        finished = true; pending.removeAll(owned); write("finished", pass, pruned);
    }

    private void stopping(ServerStoppingEvent event) {
        if (started && !finished) {
            finished = true; pending.removeAll(owned); write("aborted_server_stopping", false, false);
        }
    }

    private void write(String phase, boolean pass, boolean prunedBeforeCleanup) {
        var result = new JsonObject(); result.addProperty("run", run); result.addProperty("phase", phase);
        result.addProperty("scope", "Two synthetic offline pending-starter UUIDs; zero authenticated players, not a login/load simulation");
        result.addProperty("pass", pass); result.addProperty("server_ticks_survived", lastElapsed);
        result.addProperty("owned_offline_ids", owned.size()); result.addProperty("actual_online_players", server.getPlayerCount());
        result.addProperty("owned_ids_pruned_before_cleanup", prunedBeforeCleanup);
        result.addProperty("owned_ids_still_pending", owned.stream().filter(pending::contains).count());
        save(phase, result);
    }

    private void save(String phase, JsonObject result) {
        try {
            Path directory = Path.of("psa-starter-probe", run); Files.createDirectories(directory);
            Files.writeString(directory.resolve(String.format("%04d-%s.json", checkpoint++, phase)),
                new GsonBuilder().setPrettyPrinting().create().toJson(result) + "\n",
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        } catch (java.io.IOException failure) { throw new IllegalStateException("Starter probe evidence write failed", failure); }
    }
}
