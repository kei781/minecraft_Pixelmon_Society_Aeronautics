package dev.psa.catalogprobe.mixin;

import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Test-only counterfactual: choose which external allocator is initialized first. */
@Mixin(Player.class)
public abstract class PlayerInitializationControl {
    @Inject(method = "<clinit>", at = @At("RETURN"), require = 1)
    private static void psa$controlInitialization(CallbackInfo ci) throws ClassNotFoundException {
        String order = System.getProperty("psa.catalog.playerOrder", "natural");
        if (order.equals("natural")) return;
        String first = switch (order) {
            case "carryon-first" -> "tschipp.carryon.common.carry.CarryOnDataManager";
            case "pixelmon-first" -> "com.pixelmonmod.pixelmon.listener.EntityPlayerExtension";
            default -> throw new IllegalArgumentException("Unknown QA player order: " + order);
        };
        Class.forName(first);
        System.out.println("PSA_PLAYER_ORDER requested=" + order);
    }
}
