package dev.psa.pcsync.mixin;

import com.pixelmonmod.pixelmon.api.storage.PCStorage;
import com.pixelmonmod.pixelmon.api.storage.StorageProxy;
import com.pixelmonmod.pixelmon.listener.PixelmonPlayerTracker;
import java.util.concurrent.CompletableFuture;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.entity.player.PlayerEvent;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Sends the PC to the player once more after Pixelmon's login packets, when Pixelmon has
 * already sent it before them.
 *
 * Pixelmon 9.2.3 sends the PC from a handler that runs before this one, and the client drops
 * every PC it knows when the configuration packet sent here arrives. When the PC went out
 * first, the client ignores all later PC changes for the session: a Pokemon caught with a
 * full party is not shown, and a party Pokemon dropped on its slot appears twice.
 */
@Mixin(value = PixelmonPlayerTracker.class, remap = false)
public abstract class PixelmonPcResyncMixin {
    @Unique private static final Logger PSA_PC_RESYNC = LogManager.getLogger("PSA PC resync");

    @Inject(method = "onPlayerLogin(Lnet/minecraftforge/event/entity/player/PlayerEvent$PlayerLoggedInEvent;)V",
        at = @At("TAIL"), require = 1, expect = 1, allow = 1, remap = false)
    private static void psa$resendPcAfterLoginPackets(PlayerEvent.PlayerLoggedInEvent event, CallbackInfo callback) {
        // A failure here must never keep a player from joining; without the resend the game
        // behaves as it did before this class existed.
        try {
            if (!(event.getEntity() instanceof ServerPlayer player)) return;
            CompletableFuture<PCStorage> loading = StorageProxy.getPCForPlayer(player);
            // Still loading: Pixelmon sends the PC when the load ends, which is after the
            // configuration packet this handler has just sent. Nothing to repair.
            if (!loading.isDone()) return;
            PCStorage pc = loading.join();
            if (pc == null || player.hasDisconnected()) return;
            StorageProxy.initializePCForPlayer(player, pc);
            PSA_PC_RESYNC.debug("PC sent again after login: {}", player.getGameProfile().getName());
        } catch (Throwable problem) {
            PSA_PC_RESYNC.warn("PC was not sent again to a player after login", problem);
        }
    }
}
