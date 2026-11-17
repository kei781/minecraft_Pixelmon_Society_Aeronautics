package dev.psa.pixelmonrender;

import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexFormatElement;
import java.util.List;
import me.jellysquid.mods.sodium.client.buffer.ExtendedVertexFormat.Element;
import net.irisshaders.iris.vertices.IrisVertexFormats;

/** Validates the six original transitions once, and retains their immutable entries. */
public final class EntityAdvancePlan {
    public final int index;
    public final Element first, target;
    private final Element[] table, steps;
    private final int[] indices;

    private EntityAdvancePlan(Element[] table,Element[] steps,int[] indices,int index) {
        this.table=table;this.steps=steps;this.indices=indices;this.index=index;
        this.first=steps[0];this.target=table[index];
    }

    public static EntityAdvancePlan create(Element[] table) {
        List<VertexFormatElement> layout=IrisVertexFormats.ENTITY.m_86023_();
        List<VertexFormatElement> base=DefaultVertexFormat.f_85812_.m_86023_();
        if(table==null || table.length!=layout.size() || base.size()<6)return null;
        Element[] steps=new Element[6];int[] indices=new int[6];
        int index=0,bytes=0;
        for(int step=0;step<6;step++) {
            Element element=table[index];
            if(element==null || element.actual!=layout.get(index) || element.actual!=base.get(step)
                    || element.increment<=0 || element.increment>=table.length
                    || element.byteLength<=0 || element.byteLength>36-bytes)return null;
            steps[step]=element;indices[step]=index;bytes+=element.byteLength;
            int next=index+element.increment;
            if(next<=index || next>=table.length)return null;
            index=next;
        }
        if(bytes!=36 || table[index]==null || table[index].actual!=layout.get(index)
                || table[index].actual!=IrisVertexFormats.ENTITY_ID_ELEMENT)return null;
        return new EntityAdvancePlan(table,steps,indices,index);
    }

    public boolean matches(Element[] current) {
        if(current!=table || current[index]!=target)return false;
        for(int step=0;step<6;step++)if(current[indices[step]]!=steps[step])return false;
        return true;
    }
}
