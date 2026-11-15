package dev.psa.pixelmonrender.mixin;

import com.mojang.blaze3d.vertex.VertexConsumer;
import dev.psa.pixelmonrender.FastEntityVertexSink;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(targets = "com.pixelmonmod.pixelmon.client.models.smd.NormalizedFace", remap = false)
public abstract class PixelmonFaceMixin {
    @Redirect(method = "addFaceForRender", at = @At(value = "INVOKE",
            target = "Lcom/mojang/blaze3d/vertex/VertexConsumer;m_5954_(FFFFFFFFFIIFFF)V"),
            require = 2, allow = 2)
    private void psa$submitVertex(VertexConsumer consumer, float x, float y, float z,
            float red, float green, float blue, float alpha, float u, float v,
            int overlay, int light, float nx, float ny, float nz) {
        if (consumer instanceof FastEntityVertexSink sink && sink.psa$tryEntityVertex(
                x,y,z,red,green,blue,alpha,u,v,overlay,light,nx,ny,nz)) return;
        consumer.m_5954_(x,y,z,red,green,blue,alpha,u,v,overlay,light,nx,ny,nz);
    }
}
