package dev.psa.compat;

import com.google.common.collect.BiMap;
import com.mojang.serialization.Codec;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Initialize the pinned Pixelmon shader wire registry on both logical sides. */
@Pseudo
@Mixin(targets = "com.pixelmonmod.pixelmon.client.render.shader.PixelmonCodecs", remap = false)
public abstract class PixelmonShaderCodecMixin {
    @Shadow @Final public static BiMap<String, Codec<?>> CODECS;

    @Inject(method = "<clinit>", at = @At("RETURN"), require = 1)
    private static void psa$initializeShaderCodecs(CallbackInfo ci) {
        CODECS.putIfAbsent("int", Codec.INT);
        CODECS.putIfAbsent("float", Codec.FLOAT);
        CODECS.putIfAbsent("float_array", Codec.FLOAT.listOf());
    }
}
