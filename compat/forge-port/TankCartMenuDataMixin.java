package dev.psa.compat;

import dev.psa.menudata.MenuIntData;
import net.minecraft.world.inventory.ContainerData;
import net.minecraftforge.fluids.FluidStack;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Pseudo
@Mixin(targets = "com.alc.moreminecarts.containers.TankCartContainer", remap = false)
public abstract class TankCartMenuDataMixin {
    @Shadow(remap = false) @Final private ContainerData data;

    @ModifyArg(method = "CommonInitialization(Lnet/minecraft/world/entity/player/Inventory;)V",
            at = @At(value = "INVOKE",
                    target = "Lcom/alc/moreminecarts/containers/TankCartContainer;m_38884_(Lnet/minecraft/world/inventory/ContainerData;)V",
                    remap = false), index = 0, require = 1, expect = 1, allow = 1)
    private ContainerData psa$splitTankEntityId(ContainerData logical) {
        return MenuIntData.wire(logical);
    }

    @Inject(method = "getFluids", at = @At("HEAD"), cancellable = true, require = 1)
    private void psa$waitForCompleteTankId(CallbackInfoReturnable<FluidStack> result) {
        if (!MenuIntData.ready(data)) result.setReturnValue(null);
    }
}
