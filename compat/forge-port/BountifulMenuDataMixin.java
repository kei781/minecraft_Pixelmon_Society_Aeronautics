package dev.psa.compat;

import dev.psa.menudata.MenuIntData;
import net.minecraft.world.inventory.ContainerData;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** The board's cumulative completion count can exceed a signed menu short too. */
@Pseudo
@Mixin(targets = "io.ejekta.bountiful.content.gui.BoardScreenHandler", remap = false)
public abstract class BountifulMenuDataMixin {
    @ModifyArg(method = "<init>(ILnet/minecraft/world/entity/player/Inventory;Lio/ejekta/bountiful/content/board/BoardInventory;Lnet/minecraft/world/inventory/ContainerData;)V",
            at = @At(value = "INVOKE",
                    target = "Lio/ejekta/bountiful/content/gui/BoardScreenHandler;m_38884_(Lnet/minecraft/world/inventory/ContainerData;)V",
                    remap = false), index = 0, require = 1, expect = 1, allow = 1)
    private ContainerData psa$splitCompletionCount(ContainerData logical) {
        return MenuIntData.wire(logical);
    }
}
