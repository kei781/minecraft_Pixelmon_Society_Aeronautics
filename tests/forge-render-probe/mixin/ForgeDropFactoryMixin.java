package dev.psa.renderprobe.mixin;

import dev.psa.renderprobe.RenderProbe;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraftforge.common.ForgeInternalHandler;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Observe the exact native factory result before Forge queues it; invoke once unchanged. */
@Mixin(ForgeInternalHandler.class)
public abstract class ForgeDropFactoryMixin {
    @Redirect(method = "onEntityJoinWorld", at = @At(value = "INVOKE", target =
            "Lnet/minecraft/world/item/Item;createEntity(Lnet/minecraft/world/level/Level;Lnet/minecraft/world/entity/Entity;Lnet/minecraft/world/item/ItemStack;)Lnet/minecraft/world/entity/Entity;"),
            remap = false, require = 1, expect = 1, allow = 1)
    private Entity psa$observeFactory(Item item, Level level, Entity original, ItemStack stack) {
        Entity replacement = item.createEntity(level, original, stack);
        RenderProbe.nativeReplacement(level, original, replacement);
        return replacement;
    }
}
