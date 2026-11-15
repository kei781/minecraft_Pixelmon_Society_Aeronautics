package dev.psa.pixelmonrenderprobe;

import com.mojang.blaze3d.vertex.*;
import dev.psa.pixelmonrender.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
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
        timeBatches(original,false,data,300); timeBatches(fast,true,data,300);
        long[] a=new long[7],b=new long[7];
        for(int round=0;round<7;round++) {
            if(round%2==0) {a[round]=timeBatches(original,false,data,600);b[round]=timeBatches(fast,true,data,600);}
            else {b[round]=timeBatches(fast,true,data,600);a[round]=timeBatches(original,false,data,600);}
        }
        return ",\"cpu_microbenchmark\":{\"vertices_per_sample\":460800,\"original_ns\":"
                +Arrays.toString(a)+",\"candidate_ns\":"+Arrays.toString(b)+"}";
    }

    private static byte[] vertices(boolean fast, VertexFormat.Mode mode, int count) {
        BufferBuilder builder = new BufferBuilder(16);
        builder.m_166779_(mode,DefaultVertexFormat.f_85812_);
        if (!(((Object)builder) instanceof FastEntityVertexSink)) throw new AssertionError("adapter mixin missing");
        Random random = new Random(21);
        for (int i=0;i<count;i++) {
            float x=random.nextFloat(), y=random.nextFloat(), z=random.nextFloat();
            float u=random.nextFloat(), v=random.nextFloat();
            float nx=random.nextFloat()*4-2, ny=random.nextFloat()*4-2, nz=random.nextFloat()*4-2;
            if (fast) {
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

    private static int compareAttributes(byte[] original, byte[] candidate) {
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
                for (var method:face.getDeclaredMethods()) if(method.getName().contains("psa$submitVertex"))
                    throw new AssertionError("disabled candidate redirected face submission");
                result="{\"result\":\"PASS\",\"opt_out\":true,\"buffer_adapter_absent\":true,\"face_redirect_absent\":true}";
            } else {
            WorldRenderingSettings.INSTANCE.setUseExtendedVertexFormat(true);
            state.setCurrentEntity(32767); state.setCurrentBlockEntity(301); state.setCurrentRenderedItem(1207);
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
            }
            result="{\"result\":\"PASS\",\"vertices\":700,\"attribute_bytes\":"+bytes
                    +",\"modes\":[\"TRIANGLES\",\"QUADS\"],\"buffer_growth\":true,\"nonfinite_fallback\":true,\"normalized_face_loaded\":true"
                    +(Boolean.getBoolean("psa.render.probe.benchmark")?benchmark():"")+"}";
            }
        } catch(Throwable error) {
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
