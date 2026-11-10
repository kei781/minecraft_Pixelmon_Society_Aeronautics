package dev.psa.datapackreloadqa;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLEnvironment;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

public final class ReloadQaPlugin implements IMixinConfigPlugin {
    static final String TARGET = "net.minecraft.server.MinecraftServer";
    private static final AtomicBoolean applied = new AtomicBoolean();
    static void requireOwned() {
        try {
            Path root = Path.of("").toAbsolutePath(), marker = root.resolve(".psa-datapack-reload-qa");
            if (FMLEnvironment.dist != Dist.DEDICATED_SERVER || !Boolean.getBoolean("psa.datapackReloadQa")
                    || Files.isSymbolicLink(marker) || !Files.readString(marker).equals("psa-owned-datapack-reload-v1\n"))
                throw new IllegalStateException("Explicit owned dedicated reload QA profile required");
            var properties = new java.util.Properties();
            try (var stream = Files.newInputStream(root.resolve("server.properties"))) { properties.load(stream); }
            if (!"127.0.0.1".equals(properties.getProperty("server-ip")) || !"25574".equals(properties.getProperty("server-port")))
                throw new IllegalStateException("Fixed loopback QA endpoint required");
            Path target = root.resolve("mods/serializer_debug-1.0.1.jar");
            if (!Files.isRegularFile(target) || Files.isSymbolicLink(target)) throw new IllegalStateException("Pinned target required");
            var hash = MessageDigest.getInstance("SHA-256");
            try (var stream = Files.newInputStream(target)) {
                byte[] buffer = new byte[65536]; int count;
                while ((count = stream.read(buffer)) != -1) hash.update(buffer, 0, count);
            }
            if (!HexFormat.of().formatHex(hash.digest()).equals("fe77df10d803e08c95b9d47608444982629d2a426d1f74ac41ec569eb8fe96a8"))
                throw new IllegalStateException("Exact original SerializerDebug QA target required");
        } catch (Exception failure) { throw new IllegalStateException("Owned native reload QA refused", failure); }
    }
    static void requireApplied() {
        if (!applied.get()) throw new IllegalStateException("Native original reload-future observation required");
    }
    @Override public void onLoad(String name) { requireOwned(); }
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String target, String mixin) { return true; }
    @Override public void acceptTargets(Set<String> mine, Set<String> other) { }
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) { }
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {
        if (!TARGET.equals(target) || !"dev.psa.datapackreloadqa.mixin.ReloadFutureMixin".equals(mixin))
            throw new IllegalStateException("Exact reload observer target required");
        applied.set(true);
    }
}
