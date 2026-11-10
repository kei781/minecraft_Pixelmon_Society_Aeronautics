package dev.psa.hazardtrace;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/** Exact disposable-profile and artifact gate; never enabled in player packs. */
public final class HazardTracePlugin implements IMixinConfigPlugin {
    static final String TARGET = "com.pixelmonmod.pixelmon.api.test.notexamples.ShieldsDownRemovesHazardsTest";
    private static volatile boolean applied;
    static void requireApplied() {
        if (!applied) throw new IllegalStateException("Exact native hazard trace transformation required");
    }
    static void requireOwnedProfile() {
        try {
            Path root = Path.of("").toAbsolutePath();
            if (!Boolean.getBoolean("psa.pixelmonFixture") || !Boolean.getBoolean("psa.pixelmonHazardTrace")
                    || !Files.readString(root.resolve(".psa-pixelmon-fixture")).equals("psa-disposable-pixelmon-fixture-v1\n")
                    || !Files.readString(root.resolve(".psa-pixelmon-hazard-trace")).equals("psa-disposable-hazard-trace-v1\n"))
                throw new IllegalStateException("Explicit owned hazard diagnostic required");
            requireHash(root.resolve("mods/Pixelmon-1.20.1-9.2.3-universal.jar"),
                "8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a");
            Path baseline = root.resolve("mods/psa-hp-fixture02-baseline-r2-current.jar");
            Path patched = root.resolve("mods/psa-hp-fixture02-patched-r2-current.jar");
            if (Files.exists(baseline) == Files.exists(patched)) throw new IllegalStateException("One accepted fixture required");
            if (Files.exists(baseline)) requireHash(baseline, "26b8111035df030d44adf95e2a35eb581ecf834a6478c72776acc12284c46682");
            else requireHash(patched, "21cd4d77d0f8e9e28dff49ba0c02669abbda175cf418cd6ba9a7679bb8b4c0c5");
        } catch (Exception failure) { throw new IllegalStateException("Hazard diagnostic refused", failure); }
    }

    private static void requireHash(Path path, String expected) throws Exception {
        if (!Files.isRegularFile(path) || Files.isSymbolicLink(path)) throw new IllegalStateException("Regular pinned input required");
        var hash = MessageDigest.getInstance("SHA-256");
        try (var input = Files.newInputStream(path)) {
            byte[] block = new byte[65536]; int count;
            while ((count = input.read(block)) != -1) hash.update(block, 0, count);
        }
        if (!HexFormat.of().formatHex(hash.digest()).equals(expected)) throw new IllegalStateException("Pinned input differs");
    }

    @Override public void onLoad(String name) { requireOwnedProfile(); }
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String target, String mixin) { return true; }
    @Override public void acceptTargets(Set<String> mine, Set<String> other) { }
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) { }
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {
        if (!TARGET.equals(target) || !"dev.psa.hazardtrace.mixin.ShieldsDownTraceMixin".equals(mixin))
            throw new IllegalStateException("Unexpected hazard trace transformation");
        applied = true;
    }
}
