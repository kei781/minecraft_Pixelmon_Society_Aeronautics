package dev.psa.pixelmonrender.mixin;

import com.mojang.blaze3d.vertex.BufferBuilder;
import dev.psa.pixelmonrender.FastEntityVertexSink;
import dev.psa.pixelmonrender.NativeEntityVertex;
import java.nio.ByteBuffer;
import me.jellysquid.mods.sodium.client.render.vertex.buffer.ExtendedBufferBuilder;
import net.irisshaders.iris.vertices.IrisExtendedBufferBuilder;
import net.irisshaders.iris.vertices.IrisVertexFormats;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;

@Mixin(value = BufferBuilder.class, remap = false)
public abstract class EntityBufferMixin implements FastEntityVertexSink {
    @Shadow private ByteBuffer f_85648_;
    @Shadow private int f_85652_;
    @Shadow private int f_85656_;
    @Shadow public abstract void m_5751_();
    @Shadow public abstract void m_5752_();

    @Override
    public boolean psa$tryEntityVertex(float x, float y, float z, float red, float green,
            float blue, float alpha, float u, float v, int overlay, int light,
            float nx, float ny, float nz) {
        if (!NativeEntityVertex.ENABLED || f_85656_ != 0
                || !NativeEntityVertex.finitePosition(x,y,z)) return false;
        Object self = this;
        if (!(self instanceof IrisExtendedBufferBuilder iris)
                || !(self instanceof ExtendedBufferBuilder sodium)
                || sodium.sodium$usingFixedColor()
                || !iris.iris$extending() || iris.iris$isTerrain() || iris.iris$injectNormalAndUV1()
                || iris.iris$format() != IrisVertexFormats.ENTITY) return false;
        int stride = iris.iris$format().m_86020_();
        if (!NativeEntityVertex.canWrite(f_85648_,f_85652_,stride)) return false;
        NativeEntityVertex.write(f_85648_,f_85652_,x,y,z,red,green,blue,alpha,u,v,
                overlay,light,nx,ny,nz);
        // This six-step body stays unchanged when the separate advance mixin is disabled.
        // Its plugin adds a guarded skip only around this loop; endVertex stays original.
        for (int element = 0; element < 6; element++) m_5751_();
        m_5752_();
        return true;
    }
}
