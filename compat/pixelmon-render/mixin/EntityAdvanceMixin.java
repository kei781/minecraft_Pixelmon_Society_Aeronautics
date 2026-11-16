package dev.psa.pixelmonrender.mixin;

import com.mojang.blaze3d.vertex.*;
import dev.psa.pixelmonrender.*;
import java.nio.ByteBuffer;
import me.jellysquid.mods.sodium.client.buffer.ExtendedVertexFormat.Element;
import me.jellysquid.mods.sodium.client.render.vertex.buffer.ExtendedBufferBuilder;
import net.irisshaders.iris.vertices.IrisVertexFormats;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Check after ordinary priorities; Mixin 0.8.5 subtracts ints (see spec for extreme bounds). */
@Mixin(value=BufferBuilder.class,remap=false,priority=1 << 30)
public abstract class EntityAdvanceMixin implements FastEntityVertexAdvance {
    @Shadow private ByteBuffer f_85648_;
    @Shadow private int f_85652_;
    @Shadow private int f_85656_;
    @Shadow private VertexFormatElement f_85655_;
    @Shadow private VertexFormat f_85658_;
    @Shadow private VertexFormat.Mode f_85657_;
    // Embeddium adds these fields during MAIN; accessors resolve in the later INJECT pass.
    @Accessor("embeddium$vertexFormatExtendedElements")
    public abstract Element[] psa$getAdvanceElements();
    @Accessor("embeddium$currentExtendedElement")
    public abstract Element psa$getAdvanceElement();
    @Accessor("embeddium$currentExtendedElement")
    public abstract void psa$setAdvanceElement(Element element);
    @Unique private Element[] psa$plannedTable;
    @Unique private EntityAdvancePlan psa$advancePlan;

    @Override
    public boolean psa$tryAdvanceEntityBase() {
        Object self=this;
        if(self.getClass()!=BufferBuilder.class || f_85658_!=IrisVertexFormats.ENTITY || f_85656_!=0
                || (f_85657_!=VertexFormat.Mode.TRIANGLES && f_85657_!=VertexFormat.Mode.QUADS)
                || !(self instanceof ExtendedBufferBuilder sodium) || sodium.sodium$usingFixedColor()
                || !NativeEntityVertex.canWrite(f_85648_,f_85652_,f_85658_.m_86020_()))return false;
        Element[] table=psa$getAdvanceElements();
        if(table!=psa$plannedTable) {
            psa$plannedTable=table;psa$advancePlan=EntityAdvancePlan.create(table);
        }
        EntityAdvancePlan plan=psa$advancePlan;
        if(plan==null || !plan.matches(table) || psa$getAdvanceElement()!=plan.first
                || f_85655_!=plan.first.actual)return false;
        // Same four fields as six pinned Embeddium transitions, with no calls or data writes.
        f_85652_+=36;f_85656_=plan.index;
        psa$setAdvanceElement(plan.target);f_85655_=plan.target.actual;
        return true;
    }
}
