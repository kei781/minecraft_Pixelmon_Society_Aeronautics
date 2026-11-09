package dev.psa.catalogprobe;

import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Reads the already-constructed local player; does not alter registration order. */
@Mod.EventBusSubscriber(modid = "psacatalogprobe", value = Dist.CLIENT)
public final class ClientSchemaProbe {
    private static LocalPlayer last;
    private static int joins;

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) return;
        LocalPlayer player = Minecraft.getInstance().player;
        if (player == null || player == last) return;
        last = player;
        try {
            var schema = CatalogProbe.playerSchema(player);
            CatalogProbe.write("player-sync-client-" + (++joins) + ".json", schema);
            System.out.println("PSA_PLAYER_SCHEMA side=client " + schema);
        } catch (Throwable failure) {
            System.err.println("PSA_PLAYER_SCHEMA FAILED client");
            failure.printStackTrace();
        }
    }
}
