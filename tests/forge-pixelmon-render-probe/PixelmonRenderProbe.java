package dev.psa.pixelmonrenderprobe;

import com.mojang.blaze3d.vertex.*;
import dev.psa.pixelmonrender.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import net.irisshaders.iris.shaderpack.materialmap.WorldRenderingSettings;
import net.irisshaders.iris.uniforms.CapturedRenderingState;
import net.irisshaders.iris.vertices.IrisVertexFormats;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Separate QA mod, never included in the renderer JAR. Does not join or create a world. */
@Mod("psarenderprobe")
@Mod.EventBusSubscriber(value=Dist.CLIENT)
public final class PixelmonRenderProbe {
    private static boolean done;
    private static volatile int checksum;

    private static Object field(BufferBuilder builder,String name) throws Exception {
        Field field=BufferBuilder.class.getDeclaredField(name);field.setAccessible(true);return field.get(builder);
    }
    private record Cursor(Object offset,Object index,Object element,Object extended,Object table) { }
    private static Cursor cursor(BufferBuilder builder) throws Exception {
        return new Cursor(field(builder,"f_85652_"),field(builder,"f_85656_"),field(builder,"f_85655_"),
                field(builder,"embeddium$currentExtendedElement"),field(builder,"embeddium$vertexFormatExtendedElements"));
    }
    private static boolean advance(BufferBuilder builder) throws Exception {
        return (boolean)BufferBuilder.class.getMethod("psa$tryAdvanceEntityBase").invoke(builder);
    }
    private static void rejectUnchanged(BufferBuilder builder) throws Exception {
        Cursor before=cursor(builder);
        if(advance(builder) || !before.equals(cursor(builder)))throw new AssertionError("rejected advance changed cursor");
    }
    private static void resetBuilder(BufferBuilder builder) {
        builder.m_231175_().m_231200_();
        builder.m_85730_();
    }
    private static void writeBase(BufferBuilder builder) throws Exception {
        NativeEntityVertex.write((ByteBuffer)field(builder,"f_85648_"),(int)field(builder,"f_85652_"),
                .25f,.5f,.75f,1,1,1,1,0,0,0,0,0,1,0);
    }
    private static void finishPolygon(BufferBuilder builder,VertexFormat.Mode mode) {
        builder.m_5752_();
        int count=mode==VertexFormat.Mode.TRIANGLES?3:4;
        for(int i=1;i<count;i++)builder.m_5954_(i,0,0,1,1,1,1,0,0,0,0,0,1,0);
        resetBuilder(builder);
    }
    private static int checkAdvanceState() throws Exception {
        boolean present=Arrays.stream(BufferBuilder.class.getInterfaces()).anyMatch(
                c->c.getName().equals("dev.psa.pixelmonrender.FastEntityVertexAdvance"));
        if(present!=dev.psa.pixelmonrender.RenderCompatPlugin.advanceEnabled())
            throw new AssertionError("advance adapter does not match the effective startup setting");
        if(!present)return 0;
        int cases=0;
        BufferBuilder original=new BufferBuilder(128), candidate=new BufferBuilder(128);
        for(VertexFormat.Mode mode:new VertexFormat.Mode[]{VertexFormat.Mode.TRIANGLES,VertexFormat.Mode.QUADS}) {
            for(int repeat=0;repeat<3;repeat++) {
                original.m_166779_(mode,DefaultVertexFormat.f_85812_);
                candidate.m_166779_(mode,DefaultVertexFormat.f_85812_);
                writeBase(original);writeBase(candidate);
                for(int element=0;element<6;element++)original.m_5751_();
                boolean accepted=advance(candidate);
                if(!accepted || !cursor(original).equals(cursor(candidate)))
                    throw new AssertionError("collapsed cursor mismatch mode="+mode+" repeat="+repeat+" accepted="+accepted
                            +" expected="+cursor(original)+" actual="+cursor(candidate));
                finishPolygon(original,mode);finishPolygon(candidate,mode);cases++;
            }
        }
        BufferBuilder invalid=new BufferBuilder(128);
        invalid.m_166779_(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.f_85812_);
        invalid.m_7404_(1,2,3,4);rejectUnchanged(invalid);invalid.m_141991_();cases++;
        invalid.m_5751_();rejectUnchanged(invalid);resetBuilder(invalid);cases++;
        // Ending an incomplete vertex leaves Embeddium's element stale on same-format begin.
        // This is an invalid builder state: reject it instead of treating it as valid reuse.
        invalid.m_166779_(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.f_85812_);
        rejectUnchanged(invalid);resetBuilder(invalid);cases++;
        for(VertexFormat format:new VertexFormat[]{DefaultVertexFormat.f_85811_,DefaultVertexFormat.f_85820_}) {
            candidate.m_166779_(VertexFormat.Mode.QUADS,format);rejectUnchanged(candidate);resetBuilder(candidate);cases++;
        }
        candidate.m_166779_(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.f_85812_);
        Object[] table=(Object[])field(candidate,"embeddium$vertexFormatExtendedElements");
        Object saved=table[1];table[1]=table[0];
        try {rejectUnchanged(candidate);cases++;} finally {table[1]=saved;}
        resetBuilder(candidate);
        return cases;
    }

    private static long timeBatches(BufferBuilder builder, boolean fast, float[][] data, int batches) {
        long start=System.nanoTime();
        for (int batch=0;batch<batches;batch++) {
            builder.m_166779_(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.f_85812_);
            for (float[] a:data) {
                if (fast) {
                    if (!((FastEntityVertexSink)(Object)builder).psa$tryEntityVertex(
                            a[0],a[1],a[2],.3f,.6f,.9f,.7f,a[3],a[4],0x12345678,0x89ABCDEF,a[5],a[6],a[7]))
                        throw new AssertionError("benchmark guard rejected");
                } else builder.m_5954_(a[0],a[1],a[2],.3f,.6f,.9f,.7f,a[3],a[4],0x12345678,0x89ABCDEF,a[5],a[6],a[7]);
            }
            BufferBuilder.RenderedBuffer rendered=builder.m_231175_();
            checksum^=rendered.m_231196_().getInt(0);
            rendered.m_231200_();
        }
        return System.nanoTime()-start;
    }

    private static String benchmark() {
        float[][] data=new float[768][8]; Random random=new Random(21);
        for(float[] a:data) for(int i=0;i<a.length;i++) a[i]=random.nextFloat()*2-1;
        BufferBuilder original=new BufferBuilder(8192), fast=new BufferBuilder(8192);
        long warmStart=System.nanoTime();int warmPairs=0;
        do {
            if(warmPairs%2==0) {timeBatches(original,false,data,300);timeBatches(fast,true,data,300);}
            else {timeBatches(fast,true,data,300);timeBatches(original,false,data,300);}
            warmPairs++;
        } while(System.nanoTime()-warmStart<3_000_000_000L);
        long[] a=new long[7],b=new long[7];
        for(int round=0;round<7;round++) {
            if(round%2==0) {a[round]=timeBatches(original,false,data,600);b[round]=timeBatches(fast,true,data,600);}
            else {b[round]=timeBatches(fast,true,data,600);a[round]=timeBatches(original,false,data,600);}
        }
        return ",\"cpu_microbenchmark\":{\"vertices_per_sample\":460800,\"warmup_min_seconds\":3,\"warmup_pairs\":"+warmPairs+",\"original_ns\":"
                +Arrays.toString(a)+",\"candidate_ns\":"+Arrays.toString(b)+"}";
    }

    private static byte[] vertices(boolean fast, VertexFormat.Mode mode, int count) {
        return vertices(fast,false,mode,count);
    }
    private static byte[] vertices(boolean fast, boolean mixed, VertexFormat.Mode mode, int count) {
        BufferBuilder builder = new BufferBuilder(16);
        builder.m_166779_(mode,DefaultVertexFormat.f_85812_);
        if (!(((Object)builder) instanceof FastEntityVertexSink)) throw new AssertionError("adapter mixin missing");
        Random random = new Random(21);
        for (int i=0;i<count;i++) {
            float x=random.nextFloat(), y=random.nextFloat(), z=random.nextFloat();
            float u=random.nextFloat(), v=random.nextFloat();
            float nx=random.nextFloat()*4-2, ny=random.nextFloat()*4-2, nz=random.nextFloat()*4-2;
            if (fast && (!mixed || i%2==0)) {
                if (!((FastEntityVertexSink)(Object)builder).psa$tryEntityVertex(
                        x,y,z,.3f,.6f,.9f,.7f,u,v,0x12345678,0x89ABCDEF,nx,ny,nz))
                    throw new AssertionError("guard rejected supported entity vertex " + i);
            } else builder.m_5954_(x,y,z,.3f,.6f,.9f,.7f,u,v,0x12345678,0x89ABCDEF,nx,ny,nz);
        }
        BufferBuilder.RenderedBuffer rendered = builder.m_231175_();
        ByteBuffer bytes = rendered.m_231196_();
        byte[] result = new byte[bytes.remaining()]; bytes.get(result);
        rendered.m_231200_();
        return result;
    }

    static int compareAttributes(byte[] original, byte[] candidate) {
        if (original.length != candidate.length) throw new AssertionError("vertex length differs");
        int stride=IrisVertexFormats.ENTITY.m_86020_(), checked=0;
        boolean[] padding=new boolean[stride]; int offset=0;
        for (VertexFormatElement element : IrisVertexFormats.ENTITY.m_86023_()) {
            for (int j=0;j<element.m_86050_();j++) padding[offset+j]=element.m_86048_()==VertexFormatElement.Usage.PADDING;
            offset+=element.m_86050_();
        }
        for (int i=0;i<original.length;i++) if (!padding[i%stride]) {
            if (original[i]!=candidate[i]) throw new AssertionError("extended attribute differs at byte " + i);
            checked++;
        }
        return checked;
    }

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event) {
        String output=System.getProperty("psa.render.probe.output");
        if (done || output==null || event.phase!=TickEvent.Phase.END) return;
        done=true; String result;
        boolean previous=WorldRenderingSettings.INSTANCE.shouldUseExtendedVertexFormat();
        CapturedRenderingState state=CapturedRenderingState.INSTANCE;
        int entity=state.getCurrentRenderedEntity(), block=state.getCurrentRenderedBlockEntity(), item=state.getCurrentRenderedItem();
        try {
            Class<?> face=Class.forName("com.pixelmonmod.pixelmon.client.models.smd.NormalizedFace");
            if (!NativeEntityVertex.ENABLED) {
                BufferBuilder untouched=new BufferBuilder(16);
                if (((Object)untouched) instanceof FastEntityVertexSink)
                    throw new AssertionError("disabled candidate added adapter interface");
                if(Arrays.stream(BufferBuilder.class.getInterfaces()).anyMatch(
                        c->c.getName().equals("dev.psa.pixelmonrender.FastEntityVertexAdvance")))
                    throw new AssertionError("disabled candidate added advance interface");
                for (var method:face.getDeclaredMethods()) if(method.getName().contains("psa$submitVertex"))
                    throw new AssertionError("disabled candidate redirected face submission");
                result="{\"result\":\"PASS\",\"opt_out\":true,\"buffer_adapter_absent\":true,\"face_redirect_absent\":true}";
            } else {
            WorldRenderingSettings.INSTANCE.setUseExtendedVertexFormat(true);
            state.setCurrentEntity(32767); state.setCurrentBlockEntity(301); state.setCurrentRenderedItem(1207);
            int advanceCases=checkAdvanceState();
            BufferBuilder invalid=new BufferBuilder(16);
            invalid.m_166779_(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.f_85812_);
            if (((FastEntityVertexSink)(Object)invalid).psa$tryEntityVertex(
                    Float.intBitsToFloat(0x7FA12345),0,0,1,1,1,1,0,0,0,0,0,1,0))
                throw new AssertionError("non-finite position must fall back");
            invalid.m_85730_();
            int bytes=0;
            for (VertexFormat.Mode mode : new VertexFormat.Mode[]{VertexFormat.Mode.TRIANGLES,VertexFormat.Mode.QUADS}) {
                int count=mode==VertexFormat.Mode.TRIANGLES?300:400;
                bytes+=compareAttributes(vertices(false,mode,count),vertices(true,mode,count));
                bytes+=compareAttributes(vertices(false,mode,count),vertices(true,true,mode,count));
            }
            String timing=Boolean.getBoolean("psa.render.probe.benchmark")?benchmark():"";
            String subclass=(String)Class.forName("dev.psa.pixelmonrenderprobe.SubclassAdvanceProbe")
                    .getMethod("verify").invoke(null);
            int padding=IrisVertexFormats.ENTITY.m_86023_().stream()
                    .filter(e->e.m_86048_()==VertexFormatElement.Usage.PADDING).mapToInt(VertexFormatElement::m_86050_).sum();
            result="{\"result\":\"PASS\",\"compared_vertices\":1400,\"attribute_bytes\":"+bytes
                    +",\"modes\":[\"TRIANGLES\",\"QUADS\"],\"buffer_growth\":true,\"nonfinite_fallback\":true,\"normalized_face_loaded\":true"
                    +",\"mixed_submissions\":true,\"advance_state_cases\":"+advanceCases
                    +",\"entity_stride\":"+IrisVertexFormats.ENTITY.m_86020_()+",\"padding_bytes_per_vertex\":"+padding
                    +timing+subclass+"}";
            }
        } catch(Throwable error) {
            if(error instanceof InvocationTargetException && error.getCause()!=null)error=error.getCause();
            error.printStackTrace();
            result="{\"result\":\"FAIL\",\"error\":\""+error.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n"," ")+"\"}";
        } finally {
            WorldRenderingSettings.INSTANCE.setUseExtendedVertexFormat(previous);
            state.setCurrentEntity(entity); state.setCurrentBlockEntity(block); state.setCurrentRenderedItem(item);
        }
        try { Files.writeString(Path.of(output),result+"\n"); }
        catch(Exception error) { throw new RuntimeException(error); }
        finally { Minecraft.m_91087_().m_91395_(); }
    }
}
