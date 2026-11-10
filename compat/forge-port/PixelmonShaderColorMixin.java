package dev.psa.compat;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** Match the normalized RGBA floats consumed by Pixelmon's existing reader. */
@Pseudo
@Mixin(targets = "com.pixelmonmod.pixelmon.client.render.shader.ShaderParameters", remap = false)
public abstract class PixelmonShaderColorMixin {
    @ModifyArg(method = "lambda$static$1", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/network/FriendlyByteBuf;writeFloat(F)Lio/netty/buffer/ByteBuf;"),
            index = 0, require = 4, allow = 4)
    private static float psa$normalizeShaderColor(float component) {
        return component / 255.0F;
    }
}
