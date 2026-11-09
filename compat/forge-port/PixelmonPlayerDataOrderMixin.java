package dev.psa.compat;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Keep the two pinned mods' Player data allocations in the same order on both sides. */
@Pseudo
@Mixin(targets = "com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", remap = false)
public abstract class PixelmonPlayerDataOrderMixin {
    @Inject(method = "<clinit>", at = @At("HEAD"), require = 1)
    private static void psa$initializeCarryOnPlayerDataFirst(CallbackInfo ci) {
        try {
            // The merged caller uses Pixelmon's mod classloader. No accessor IDs are hardcoded.
            Class.forName("tschipp.carryon.common.carry.CarryOnDataManager");
        } catch (ClassNotFoundException absentOptionalCarryOn) {
            // Carry On belongs to Society; the separate minimal diagnostic pack omits it.
        }
    }
}
