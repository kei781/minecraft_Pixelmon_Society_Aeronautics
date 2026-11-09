package dev.psa.pixelmonfixture;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/** Refuse accidental deployment or a different upstream binary before mixing tests. */
public final class FixtureMixinPlugin implements IMixinConfigPlugin {
    private static final Set<String> APPLIED = java.util.concurrent.ConcurrentHashMap.newKeySet();
    public static void requireApplied(Set<String> expected) {
        if (!APPLIED.equals(expected))
            throw new IllegalStateException("Exact ten fixture transformations required; applied=" + APPLIED.size());
    }
    public static void requireOwnedProfile() {
        try {
            Path root = Path.of("").toAbsolutePath();
            if (!Boolean.getBoolean("psa.pixelmonFixture") || !Files.readString(root.resolve(".psa-pixelmon-fixture"))
                    .equals("psa-disposable-pixelmon-fixture-v1\n"))
                throw new IllegalStateException("Owned disposable fixture opt-in required");
            Path jar = root.resolve("mods/Pixelmon-1.20.1-9.2.3-universal.jar");
            var digest = MessageDigest.getInstance("SHA-256");
            try (var stream = Files.newInputStream(jar)) {
                byte[] block = new byte[65536]; int size;
                while ((size = stream.read(block)) != -1) digest.update(block, 0, size);
            }
            if (!HexFormat.of().formatHex(digest.digest()).equals(
                    "8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a"))
                throw new IllegalStateException("Pinned Pixelmon binary differs");
        } catch (Exception failure) { throw new IllegalStateException("Fixture profile refused", failure); }
    }
    @Override public void onLoad(String mixinPackage) { requireOwnedProfile(); }
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String target, String mixin) { return true; }
    @Override public void acceptTargets(Set<String> mine, Set<String> other) { }
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) { }
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {
        if (!mixin.startsWith("dev.psa.pixelmonfixture.mixin."))
            throw new IllegalStateException("Unexpected fixture mixin");
        APPLIED.add(target);
    }
}
