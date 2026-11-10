package dev.psa.startercompat.mixin;

import com.pixelmonmod.pixelmon.TickHandler;
import com.pixelmonmod.pixelmon.api.util.helpers.NetworkHelper;
import com.pixelmonmod.pixelmon.comm.data.PixelmonPacket;
import java.util.Set;
import java.util.UUID;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.server.ServerLifecycleHooks;
import org.objectweb.asm.Opcodes;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Only the pending starter-screen retry batch; never changes party/storage data. */
@Mixin(value = TickHandler.class, remap = false)
public abstract class PixelmonStarterRecipientMixin {
    @Shadow @Final private static Set<UUID> playerListForStartMenu;
    @Shadow private int worldCounter;

    @Redirect(method = "onServerTick", at = @At(value = "INVOKE", target =
        "Lcom/pixelmonmod/pixelmon/api/util/helpers/NetworkHelper;sendPacket(Lnet/minecraft/server/level/ServerPlayer;Lcom/pixelmonmod/pixelmon/comm/data/PixelmonPacket;)V"),
        require = 1, expect = 1, allow = 1, remap = false)
    private void psa$sendStarterToConnectedPlayer(ServerPlayer player, PixelmonPacket packet) {
        if (player != null) NetworkHelper.sendPacket(player, packet);
    }

    @Inject(method = "onServerTick", at = @At(value = "FIELD", target =
        "Lcom/pixelmonmod/pixelmon/TickHandler;worldCounter:I", opcode = Opcodes.PUTFIELD, shift = At.Shift.AFTER),
        require = 1, expect = 1, allow = 1, remap = false)
    private void psa$expireOfflineStarterRequests(TickEvent.ServerTickEvent event, CallbackInfo callback) {
        // The original batch runs every 100 ticks, before this final increment.
        // Prune only after iteration so the native iterator is never invalidated.
        if (event.phase != TickEvent.Phase.END || (worldCounter - 1) % 100 != 0) return;
        var server = ServerLifecycleHooks.getCurrentServer();
        if (server != null) playerListForStartMenu.removeIf(id -> server.getPlayerList().getPlayer(id) == null);
    }
}
