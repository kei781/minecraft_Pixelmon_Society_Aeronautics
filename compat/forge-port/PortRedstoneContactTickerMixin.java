package dev.psa.portfix.mixin;

import com.simibubi.create.content.redstone.contact.RedstoneContactBlock;
import com.simibubi.create.foundation.blockEntity.SmartBlockEntityTicker;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntityTicker;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * The port gives Create's Redstone Contact a block entity; its getTicker ends in
 * IBE.super.getTicker(...), which this pack's Mixin rebinds to the block class itself, and the JVM
 * refuses that call. A placed contact stopped the server, and again whenever its chunk loaded.
 * This answers before that call is reached, with what IBE.getTicker returns for a SmartBlockEntity.
 */
@Mixin(value = RedstoneContactBlock.class, remap = false)
public abstract class PortRedstoneContactTickerMixin {
    // m_142354_ is getTicker as the port's own mixin adds it to this class.
    @Inject(method = "m_142354_", at = @At("HEAD"), cancellable = true, require = 1, expect = 1, allow = 1, remap = false)
    private void psa$tickerWithoutInterfaceSuper(Level level, BlockState state, BlockEntityType<?> type,
                                                 CallbackInfoReturnable<BlockEntityTicker<?>> callback) {
        callback.setReturnValue(level.isClientSide ? null : new SmartBlockEntityTicker<>());
    }
}
