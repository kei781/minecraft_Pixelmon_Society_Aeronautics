package dev.psa.renderprobe.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import dev.psa.renderprobe.RenderClient;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.EntityRenderDispatcher;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** SRG names pinned to Minecraft1.20.1, Forge47.4.20; never cancel or replace rendering. */
@Mixin(EntityRenderDispatcher.class)
public abstract class RendererProbeMixin {
    @Inject(method = "m_114384_", at = @At("HEAD"), remap = false, require = 1, expect = 1, allow = 1)
    private void psa$before(Entity entity, double x, double y, double z, float yaw, float partialTick,
            PoseStack pose, MultiBufferSource buffers, int light, CallbackInfo callback) {
        RenderClient.before(entity);
    }
    @Inject(method = "m_114384_", at = @At("TAIL"), remap = false, require = 1, expect = 1, allow = 1)
    private void psa$after(Entity entity, double x, double y, double z, float yaw, float partialTick,
            PoseStack pose, MultiBufferSource buffers, int light, CallbackInfo callback) {
        RenderClient.after(entity);
    }
}
