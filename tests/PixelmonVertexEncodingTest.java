package dev.psa.pixelmonrender;

import com.mojang.blaze3d.vertex.*;
import java.nio.*;
import java.util.*;
import org.lwjgl.system.MemoryUtil;

/** Compares authored stores to Minecraft's real default consumer, not a copy of its packing code. */
public final class PixelmonVertexEncodingTest {
    private static final int START = 16;
    private static int cases;

    private static final class Original implements BufferVertexConsumer {
        final ByteBuffer bytes;
        int element, offset = START;
        final List<VertexFormatElement> elements = DefaultVertexFormat.f_85812_.m_86023_();
        Original(ByteBuffer bytes) { this.bytes = bytes; }
        public VertexFormatElement m_6297_() { return elements.get(element); }
        public void m_5751_() {
            offset += m_6297_().m_86050_();
            element = (element + 1) % elements.size();
            if (m_6297_().m_86048_() == VertexFormatElement.Usage.PADDING) m_5751_();
        }
        public void m_5672_(int index, byte value) { bytes.put(offset + index, value); }
        public void m_5586_(int index, short value) { bytes.putShort(offset + index, value); }
        public void m_5832_(int index, float value) { bytes.putFloat(offset + index, value); }
        public void m_5752_() { if (element != 0) throw new AssertionError("unfinished vertex"); }
        public void m_7404_(int r, int g, int b, int a) { throw new UnsupportedOperationException(); }
        public void m_141991_() { }
    }

    private static void compare(float[] a, int overlay, int light) {
        ByteBuffer expected = MemoryUtil.memAlloc(96).order(ByteOrder.LITTLE_ENDIAN);
        ByteBuffer actual = MemoryUtil.memAlloc(96).order(ByteOrder.LITTLE_ENDIAN);
        try {
            for (int i = 0; i < 96; i++) { expected.put(i, (byte)0xA5); actual.put(i, (byte)0xA5); }
            new Original(expected).m_5954_(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],
                    overlay,light,a[9],a[10],a[11]);
            NativeEntityVertex.write(actual, START, a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],
                    overlay,light,a[9],a[10],a[11]);
            for (int i = 0; i < 96; i++) if (expected.get(i) != actual.get(i))
                throw new AssertionError("byte mismatch at " + i + " case=" + cases);
            cases++;
        } finally { MemoryUtil.memFree(expected); MemoryUtil.memFree(actual); }
    }

    public static void main(String[] args) {
        String priorFlag=System.getProperty("psa.pixelmon.fastVertices");
        String priorAdvance=System.getProperty("psa.pixelmon.fastAdvance");
        try {
            System.clearProperty("psa.pixelmon.fastAdvance");
            System.clearProperty("psa.pixelmon.fastVertices");
            RenderCompatPlugin off=new RenderCompatPlugin(); off.onLoad("ignored");
            if(off.shouldApplyMixin("BufferBuilder","EntityBufferMixin")
                    || off.shouldApplyMixin("NormalizedFace","PixelmonFaceMixin"))
                throw new AssertionError("disabled candidate must not transform classes");
            System.setProperty("psa.pixelmon.fastVertices","true");
            RenderCompatPlugin on=new RenderCompatPlugin(); on.onLoad("ignored");
            if(!on.shouldApplyMixin("BufferBuilder","EntityBufferMixin")
                    || !on.shouldApplyMixin("NormalizedFace","PixelmonFaceMixin"))
                throw new AssertionError("explicit opt-in must apply both mixins");
            if(on.shouldApplyMixin("BufferBuilder","dev.psa.pixelmonrender.mixin.EntityAdvanceMixin"))
                throw new AssertionError("advance must require its own explicit opt-in");
            System.setProperty("psa.pixelmon.fastAdvance","true");
            RenderCompatPlugin both=new RenderCompatPlugin(); both.onLoad("ignored");
            if(!both.shouldApplyMixin("BufferBuilder","dev.psa.pixelmonrender.mixin.EntityAdvanceMixin"))
                throw new AssertionError("both flags must enable advance");
            System.clearProperty("psa.pixelmon.fastVertices");
            RenderCompatPlugin advanceOnly=new RenderCompatPlugin(); advanceOnly.onLoad("ignored");
            if(advanceOnly.shouldApplyMixin("BufferBuilder","dev.psa.pixelmonrender.mixin.EntityAdvanceMixin"))
                throw new AssertionError("advance alone must not transform classes");
        } finally {
            if(priorFlag==null) System.clearProperty("psa.pixelmon.fastVertices");
            else System.setProperty("psa.pixelmon.fastVertices",priorFlag);
            if(priorAdvance==null) System.clearProperty("psa.pixelmon.fastAdvance");
            else System.setProperty("psa.pixelmon.fastAdvance",priorAdvance);
        }
        float[] edge = {0f,-0f,1f,-1f,0.5f,-0.5f,1.01f,-1.01f,Float.NaN,
                Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY,Float.MIN_VALUE,Float.MAX_VALUE};
        for (float value : edge) {
            float[] attributes = new float[12]; Arrays.fill(attributes, value);
            // Non-finite positions retain the original float->double->float path.
            if (!Float.isFinite(value)) attributes[0]=attributes[1]=attributes[2]=0;
            compare(attributes, 0x89ABCDEF, 0x12345678);
        }
        for (int bits : new int[]{0x7FA12345, 0xFFA12345, 0x7FC12345}) {
            float[] attributes = new float[12]; Arrays.fill(attributes,Float.intBitsToFloat(bits));
            attributes[0]=attributes[1]=attributes[2]=0;
            compare(attributes,0,0);
        }
        if (!NativeEntityVertex.finitePosition(0,-0f,Float.MAX_VALUE)
                || NativeEntityVertex.finitePosition(Float.NaN,0,0)
                || NativeEntityVertex.finitePosition(0,Float.POSITIVE_INFINITY,0)
                || NativeEntityVertex.finitePosition(0,0,Float.NEGATIVE_INFINITY))
            throw new AssertionError("position fallback guard");
        Random random = new Random(21);
        for (int n = 0; n < 10000; n++) {
            float[] a = new float[12];
            for (int i = 0; i < a.length; i++) a[i] = random.nextFloat()*8-4;
            compare(a, random.nextInt(), random.nextInt());
        }
        ByteBuffer direct = MemoryUtil.memAlloc(128).order(ByteOrder.LITTLE_ENDIAN);
        try {
            if (!NativeEntityVertex.canWrite(direct, 16, 56)) throw new AssertionError("valid bounds");
            if (NativeEntityVertex.canWrite(direct, -1, 56)
                    || NativeEntityVertex.canWrite(direct, Integer.MAX_VALUE, 56)
                    || NativeEntityVertex.canWrite(direct, 80, 56)
                    || NativeEntityVertex.canWrite(direct.asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN),16,56)
                    || NativeEntityVertex.canWrite(ByteBuffer.allocate(128).order(ByteOrder.LITTLE_ENDIAN),16,56)
                    || NativeEntityVertex.canWrite(direct.duplicate().order(ByteOrder.BIG_ENDIAN),16,56))
                throw new AssertionError("unsafe buffer accepted");
            direct.limit(64);
            if (NativeEntityVertex.canWrite(direct,16,56)) throw new AssertionError("limit ignored");
        } finally { MemoryUtil.memFree(direct); }
        System.out.println("PASS original Minecraft vertex bytes: " + cases + "; buffer guards: 7; position guards: 4");
    }
}
