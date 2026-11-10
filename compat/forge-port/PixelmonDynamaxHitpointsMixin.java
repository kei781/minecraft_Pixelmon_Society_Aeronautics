package dev.psa.compat;

import com.pixelmonmod.pixelmon.api.pokemon.Pokemon;
import com.pixelmonmod.pixelmon.api.pokemon.stats.BattleStatsType;
import com.pixelmonmod.pixelmon.api.registries.PixelmonSpecies;
import com.pixelmonmod.pixelmon.battles.controller.participants.PixelmonWrapper;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Match the native transition's Shedinja exception in the maximum-HP query. */
@Mixin(value = PixelmonWrapper.class, remap = false)
public abstract class PixelmonDynamaxHitpointsMixin {
    @Shadow public Pokemon pokemon;
    @Shadow public int isDynamax;

    @Inject(method = "getMaxHealth(Z)I", at = @At("RETURN"),
        cancellable = true, require = 1, expect = 1, allow = 1, remap = false)
    private void psa$preserveShedinjaHitpoint(boolean ignoreDynamax, CallbackInfoReturnable<Integer> result) {
        if (!ignoreDynamax && isDynamax > 0
                && pokemon.getSpecies().is(PixelmonSpecies.SHEDINJA)
                && pokemon.getStat(BattleStatsType.HP) == 1)
            result.setReturnValue(1);
    }
}
