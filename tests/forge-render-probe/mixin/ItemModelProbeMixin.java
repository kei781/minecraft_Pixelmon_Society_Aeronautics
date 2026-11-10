package dev.psa.renderprobe.mixin;

import dev.psa.renderprobe.RenderClient;
import net.minecraft.client.renderer.entity.ItemRenderer;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(ItemRenderer.class)
public abstract class ItemModelProbeMixin {
    @Inject(method = "m_174264_", at = @At("RETURN"), remap = false, require = 1, expect = 1, allow = 1)
    private void psa$model(ItemStack stack, Level level, LivingEntity entity, int seed, CallbackInfoReturnable<BakedModel> callback) {
        RenderClient.model(stack, callback.getReturnValue());
    }
}
