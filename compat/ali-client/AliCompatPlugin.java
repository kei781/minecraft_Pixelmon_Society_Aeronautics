package dev.psa.alicompat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/** Also checked by the mandatory mod constructor, not only the Mixin plugin. */
public final class AliCompatPlugin implements IMixinConfigPlugin {
    static final String TARGET = "com.yanny.aci.tooltip.TooltipNode";
    static final String BUILDER_TARGET = "com.yanny.aci.tooltip.TooltipBuilder";
    private static final AtomicInteger applied = new AtomicInteger();

    static void requirePinnedInput() {
        try {
            Path input = Path.of("mods/AdvancedLootInfo-forge-1.20.1-1.12.0.jar");
            if (!Files.isRegularFile(input) || Files.isSymbolicLink(input))
                throw new IllegalStateException("Regular pinned ALI input required");
            var hash = MessageDigest.getInstance("SHA-256");
            try (var stream = Files.newInputStream(input)) {
                byte[] block = new byte[65536]; int count;
                while ((count = stream.read(block)) != -1) hash.update(block, 0, count);
            }
            if (!HexFormat.of().formatHex(hash.digest()).equals("6a0b368a0c19476ce1c6e73ecd923855e5ef45834077dea1ae0ca94820ce8eb8"))
                throw new IllegalStateException("ALI binary identity differs");
        } catch (java.io.IOException | java.security.NoSuchAlgorithmException failure) {
            throw new IllegalStateException("Pinned ALI compatibility refused", failure);
        }
    }

    static void requireApplied() {
        if (applied.get() != 3) throw new IllegalStateException("Both exact ALI tooltip transformations required");
    }

    @Override public void onLoad(String name) { requirePinnedInput(); }
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String target, String mixin) { return true; }
    @Override public void acceptTargets(Set<String> mine, Set<String> other) { }
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) { }
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {
        int bit;
        if (TARGET.equals(target) && "dev.psa.alicompat.mixin.AliTooltipPaletteMixin".equals(mixin)) bit = 1;
        else if (BUILDER_TARGET.equals(target) && "dev.psa.alicompat.mixin.AliTooltipBuilderPaletteMixin".equals(mixin)) bit = 2;
        else throw new IllegalStateException("Unexpected ALI compatibility transformation");
        applied.getAndUpdate(previous -> previous | bit);
    }
}
