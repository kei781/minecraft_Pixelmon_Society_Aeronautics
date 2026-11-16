package dev.psa.pixelmonrender;

import java.util.List;
import java.util.Set;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/** Off means neither target is transformed, not merely a branch inside the renderer. */
public final class RenderCompatPlugin implements IMixinConfigPlugin {
    private boolean enabled;
    private boolean advance;
    @Override public void onLoad(String mixinPackage) {
        enabled=Boolean.getBoolean("psa.pixelmon.fastVertices");
        advance=Boolean.getBoolean("psa.pixelmon.fastAdvance");
    }
    @Override public boolean shouldApplyMixin(String target, String mixin) {
        return enabled && (!mixin.endsWith("EntityAdvanceMixin") || advance);
    }
    @Override public String getRefMapperConfig() { return null; }
    @Override public List<String> getMixins() { return null; }
    @Override public void acceptTargets(Set<String> own, Set<String> other) { }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) { }
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {
        if(mixin.endsWith("EntityAdvanceMixin"))AdvanceCompatibility.configure(node);
    }
}
