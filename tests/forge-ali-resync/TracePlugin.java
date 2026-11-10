package dev.psa.aliresync;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLEnvironment;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

public final class TracePlugin implements IMixinConfigPlugin {
    static final String TARGET = "com.yanny.aci.tooltip.TooltipNodePalette";
    private static final java.util.concurrent.atomic.AtomicInteger applied = new java.util.concurrent.atomic.AtomicInteger();
    static void requireOwned() {
        try {
            Path root = Path.of("").toAbsolutePath(), marker = root.resolve(".psa-ali-resync-trace");
            boolean opted = FMLEnvironment.dist == Dist.CLIENT ? Boolean.getBoolean("psa.modelAudit") : Boolean.getBoolean("psa.aliResyncTrace");
            if (!opted || Files.isSymbolicLink(marker) || !Files.readString(marker).equals("psa-owned-ali-resync-v1\n"))
                throw new IllegalStateException("Explicit owned ALI resync QA profile required");
            requireHash(root.resolve("mods/AdvancedLootInfo-forge-1.20.1-1.12.0.jar"), "6a0b368a0c19476ce1c6e73ecd923855e5ef45834077dea1ae0ca94820ce8eb8");
            requireHash(root.resolve("mods/psa-aeronautics-experimental-forge-1.20.1.jar"), "351ecb0905a7f05a262a9401fe0e968402896f527e5983838ef2014641e3a3db");
            requireHash(root.resolve("mods/Pixelmon-1.20.1-9.2.3-universal.jar"), "8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a");
        } catch (Exception failure) { throw new IllegalStateException("ALI resync QA refused", failure); }
    }
    private static void requireHash(Path input, String expected) throws Exception {
        if (!Files.isRegularFile(input) || Files.isSymbolicLink(input)) throw new IllegalStateException("Regular pinned input required");
        var hash = MessageDigest.getInstance("SHA-256");
        try (var stream = Files.newInputStream(input)) {
            byte[] block = new byte[65536]; int count;
            while ((count = stream.read(block)) != -1) hash.update(block, 0, count);
        }
        if (!HexFormat.of().formatHex(hash.digest()).equals(expected)) throw new IllegalStateException("Pinned resync input differs");
    }
    static void requireApplied() {
        int expected = FMLEnvironment.dist == Dist.CLIENT ? 3 : 1;
        if (applied.get() != expected) throw new IllegalStateException("All actual native resync trace transformations required");
    }
    @Override public void onLoad(String name) { requireOwned(); }
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String target, String mixin) { return true; }
    @Override public void acceptTargets(Set<String> mine, Set<String> other) { }
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) { }
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {
        int bit;
        if (TARGET.equals(target) && "dev.psa.aliresync.mixin.PaletteTraceMixin".equals(mixin)) bit = 1;
        else if ("com.yanny.ali.emi.compatibility.EmiCompatibility".equals(target)
                && "dev.psa.aliresync.mixin.RegistrationTraceMixin".equals(mixin)) bit = 2;
        else throw new IllegalStateException("Unexpected resync trace target");
        applied.getAndUpdate(previous -> previous | bit);
    }
}
