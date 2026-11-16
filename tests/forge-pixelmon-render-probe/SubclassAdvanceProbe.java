package dev.psa.pixelmonrenderprobe;

import com.mojang.blaze3d.vertex.*;
import dev.psa.pixelmonrender.*;
import java.lang.reflect.Field;
import java.nio.ByteBuffer;
import java.util.List;

/** Loaded after timed work so the test subclass does not change benchmark class hierarchy. */
public final class SubclassAdvanceProbe {
    private static final class CountingBuilder extends BufferBuilder {
        int calls;
        CountingBuilder() { super(128); }
        @Override public void m_5751_() { calls++;super.m_5751_(); }
    }
    private static Object field(BufferBuilder builder,String name) throws Exception {
        Field field=BufferBuilder.class.getDeclaredField(name);field.setAccessible(true);return field.get(builder);
    }
    private static List<Object> cursor(BufferBuilder builder) throws Exception {
        return List.of(field(builder,"f_85652_"),field(builder,"f_85656_"),field(builder,"f_85655_"),
                field(builder,"embeddium$currentExtendedElement"));
    }
    private static byte[] submit(CountingBuilder builder,boolean fast) {
        builder.m_166779_(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.f_85812_);
        for(int i=0;i<6;i++) {
            if(fast) {
                if(!((FastEntityVertexSink)(Object)builder).psa$tryEntityVertex(
                        i,.5f,.75f,1,1,1,1,0,0,0x12345678,0x89ABCDEF,0,1,0))
                    throw new AssertionError("Native subclass fallback rejected supported base submission");
            } else builder.m_5954_(i,.5f,.75f,1,1,1,1,0,0,0x12345678,0x89ABCDEF,0,1,0);
        }
        BufferBuilder.RenderedBuffer rendered=builder.m_231175_();
        ByteBuffer bytes=rendered.m_231196_();byte[] result=new byte[bytes.remaining()];bytes.get(result);
        rendered.m_231200_();return result;
    }
    public static String verify() throws Exception {
        int guardCases=0;
        if(Boolean.getBoolean("psa.pixelmon.fastAdvance")) {
            CountingBuilder builder=new CountingBuilder();
            builder.m_166779_(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.f_85812_);
            List<Object> before=cursor(builder);
            if(((FastEntityVertexAdvance)(Object)builder).psa$tryAdvanceEntityBase())
                throw new AssertionError("BufferBuilder subclass must retain its virtual nextElement calls");
            if(builder.calls!=0 || !before.equals(cursor(builder)))throw new AssertionError("Subclass rejection changed state");
            builder.m_231175_().m_231200_();guardCases++;
        }
        CountingBuilder original=new CountingBuilder(),candidate=new CountingBuilder();
        int checked=PixelmonRenderProbe.compareAttributes(submit(original,false),submit(candidate,true));
        if(original.calls<=0 || candidate.calls!=original.calls)
            throw new AssertionError("Subclass nextElement override was skipped: "+original.calls+"/"+candidate.calls);
        return ",\"subclass_guard_cases\":"+guardCases+",\"subclass_override_calls\":"+candidate.calls
                +",\"subclass_attribute_bytes\":"+checked;
    }
}
