package dev.psa.discountprobe.mixin;

import dev.psa.discountprobe.DiscountProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** Observe the real server factory's constructor input without changing it. */
@Mixin(targets = "io.ejekta.bountiful.content.BountyCreator$Companion", remap = false)
public abstract class FactoryArgumentMixin {
    @ModifyArg(method = "createBountyItem", at = @At(value = "INVOKE",
            target = "Lio/ejekta/bountiful/content/BountyCreator;<init>(Lnet/minecraft/server/level/ServerLevel;Lnet/minecraft/core/BlockPos;Ljava/util/Set;IJLkotlin/jvm/internal/DefaultConstructorMarker;)V",
            remap = false), index = 3, require = 1, expect = 1, allow = 1)
    private int psa$observeActualFactoryReputation(int original) {
        DiscountProbe.observeFactoryArgument(original);
        return original;
    }
}
