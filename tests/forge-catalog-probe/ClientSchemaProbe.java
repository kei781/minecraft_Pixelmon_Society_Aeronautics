package dev.psa.catalogprobe;

import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;

/** Reads the already-constructed local player; does not alter registration order. */
@Mod.EventBusSubscriber(modid = "psacatalogprobe", value = Dist.CLIENT)
public final class ClientSchemaProbe {
    private static LocalPlayer last;
    private static boolean connected;
    private static int sessions;
    private static int snapshots;

    @SubscribeEvent
    public static void login(ClientPlayerNetworkEvent.LoggingIn event) {
        connected = true;
        sessions++;
        snapshots = 0;
        last = null;
    }

    @SubscribeEvent
    public static void logout(ClientPlayerNetworkEvent.LoggingOut event) {
        connected = false;
        last = null;
    }

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) return;
        LocalPlayer player = Minecraft.getInstance().player;
        if (!connected || player == null || player == last) return;
        last = player;
        try {
            var schema = CatalogProbe.playerSchema(player);
            schema.addProperty("connection_session", sessions);
            schema.addProperty("player_snapshot", ++snapshots);
            schema.addProperty("session_started_by", "ClientPlayerNetworkEvent.LoggingIn");
            CatalogProbe.write("player-sync-session-" + sessions + "-player-" + snapshots + ".json", schema);
            System.out.println("PSA_PLAYER_SCHEMA side=client " + schema);
        } catch (Throwable failure) {
            System.err.println("PSA_PLAYER_SCHEMA FAILED client");
            failure.printStackTrace();
        }
    }
}
