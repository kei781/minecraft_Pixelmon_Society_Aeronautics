package dev.psa.clientmenu.mixin;

import net.minecraft.util.Mth;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** Match the reputation range used by Bountiful's server-side bounty factory. */
@Pseudo
@Mixin(targets = "io.ejekta.bountiful.content.BountyCreator$Companion", remap = false)
public abstract class BountifulDiscountMixin {
    @ModifyVariable(method = "getDiscount(I)D", at = @At("HEAD"), argsOnly = true,
            ordinal = 0, require = 1, expect = 1, allow = 1)
    private int psa$useServerReputationRange(int reputation) {
        return Mth.clamp(reputation, -30, 30);
    }
}
