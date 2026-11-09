package dev.psa.compat;

import dev.psa.menudata.MenuIntData;
import net.minecraft.world.inventory.MenuType;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

@Pseudo
@Mixin(targets = "com.alc.moreminecarts.containers.BatteryCartContainer", remap = false)
public abstract class BatteryCartMenuTypeMixin {
    @ModifyArg(method = "<init>(ILnet/minecraft/world/level/Level;Lnet/minecraft/world/entity/player/Inventory;Lnet/minecraft/world/entity/player/Player;)V",
            at = @At(value = "INVOKE",
                    target = "Lnet/minecraft/world/inventory/AbstractContainerMenu;<init>(Lnet/minecraft/world/inventory/MenuType;I)V",
                    remap = false), index = 0, require = 1, expect = 1, allow = 1)
    private static MenuType<?> psa$useBatteryMenuType(MenuType<?> original) {
        return MenuIntData.batteryMenuType();
    }
}
