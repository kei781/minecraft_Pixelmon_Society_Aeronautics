package dev.psa.pixelmonrender;

import com.mojang.blaze3d.vertex.BufferVertexConsumer;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import org.lwjgl.system.MemoryUtil;

/** Exact NEW_ENTITY base attributes. The caller retains Iris's completion hooks. */
public final class NativeEntityVertex {
    public static final boolean ENABLED = RenderCompatPlugin.verticesEnabled();
    private NativeEntityVertex() { }

    public static boolean finitePosition(float x, float y, float z) {
        return Float.isFinite(x) && Float.isFinite(y) && Float.isFinite(z);
    }

    public static boolean canWrite(ByteBuffer buffer, int offset, int stride) {
        return buffer != null && buffer.isDirect() && !buffer.isReadOnly()
                && ByteOrder.nativeOrder() == ByteOrder.LITTLE_ENDIAN
                && buffer.order() == ByteOrder.LITTLE_ENDIAN
                && offset >= 0 && stride >= 36 && offset <= buffer.limit() - stride;
    }

    /** Requires finitePosition and canWrite(buffer, offset, actualStride) before native access. */
    public static void write(ByteBuffer buffer, int offset, float x, float y, float z,
            float red, float green, float blue, float alpha, float u, float v,
            int overlay, int light, float nx, float ny, float nz) {
        long address = MemoryUtil.memAddress(buffer, offset);
        MemoryUtil.memPutFloat(address, x);
        MemoryUtil.memPutFloat(address + 4, y);
        MemoryUtil.memPutFloat(address + 8, z);
        int color = ((int)(red * 255) & 255) | (((int)(green * 255) & 255) << 8)
                | (((int)(blue * 255) & 255) << 16) | (((int)(alpha * 255) & 255) << 24);
        MemoryUtil.memPutInt(address + 12, color);
        MemoryUtil.memPutFloat(address + 16, u);
        MemoryUtil.memPutFloat(address + 20, v);
        MemoryUtil.memPutInt(address + 24, overlay);
        MemoryUtil.memPutInt(address + 28, light);
        // Use the original clamp/NaN behavior, including normals outside [-1, 1].
        MemoryUtil.memPutByte(address + 32, BufferVertexConsumer.m_85774_(nx));
        MemoryUtil.memPutByte(address + 33, BufferVertexConsumer.m_85774_(ny));
        MemoryUtil.memPutByte(address + 34, BufferVertexConsumer.m_85774_(nz));
        // Padding byte 35 and every Iris attribute are left to their original owners.
    }
}
