package dev.psa.datapacksync.mixin;

import net.minecraftforge.event.OnDatapackSyncEvent;
import net.minecraftforge.network.PacketDistributor;
import net.minecraftforge.network.simple.SimpleChannel;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Null player is Forge's all-player event, not a missing individual recipient. */
@Mixin(targets = "com.dairymoose.sd.SerializerDebugCommon", remap = false)
public abstract class SerializerDebugDatapackMixin {
    @Redirect(method = "onPlayerDatapackSync", remap = false, require = 1, expect = 1, allow = 1,
        at = @At(value = "INVOKE", remap = false,
            target = "Lnet/minecraftforge/network/simple/SimpleChannel;send(Lnet/minecraftforge/network/PacketDistributor$PacketTarget;Ljava/lang/Object;)V"))
    private void psa$sendToDatapackRecipients(SimpleChannel channel, PacketDistributor.PacketTarget target,
            Object packet, OnDatapackSyncEvent event) {
        if (event.getPlayer() != null) {
            channel.send(target, packet);
            return;
        }
        for (var player : event.getPlayers())
            channel.send(PacketDistributor.PLAYER.with(() -> player), packet);
    }
}
