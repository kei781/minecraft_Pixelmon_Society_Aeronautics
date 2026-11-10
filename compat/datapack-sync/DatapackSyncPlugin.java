package dev.psa.datapacksync;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLEnvironment;
import net.minecraftforge.fml.loading.FMLPaths;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.MethodInsnNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

public final class DatapackSyncPlugin implements IMixinConfigPlugin {
    static final String TARGET = "com.dairymoose.sd.SerializerDebugCommon";
    static final String EVENT_DESCRIPTOR = "(Lnet/minecraftforge/event/OnDatapackSyncEvent;)V";
    static final String SEND_DESCRIPTOR = "(Lnet/minecraftforge/network/PacketDistributor$PacketTarget;Ljava/lang/Object;)V";
    static final String HANDLER_DESCRIPTOR = "(Lnet/minecraftforge/network/simple/SimpleChannel;Lnet/minecraftforge/network/PacketDistributor$PacketTarget;Ljava/lang/Object;Lnet/minecraftforge/event/OnDatapackSyncEvent;)V";
    private static final AtomicBoolean applied = new AtomicBoolean();

    static void requirePinnedInput() { requirePinnedDirectory(FMLPaths.GAMEDIR.get()); }

    static void requirePinnedDirectory(Path directory) {
        try {
            Path mods = directory.resolve("mods"), input = mods.resolve("serializer_debug-1.0.1.jar");
            if (Files.isSymbolicLink(mods) || Files.isSymbolicLink(input) || !Files.isRegularFile(input))
                throw new IllegalStateException("Regular pinned SerializerDebug input required");
            var hash = MessageDigest.getInstance("SHA-256");
            try (var stream = Files.newInputStream(input)) {
                byte[] buffer = new byte[65536]; int count;
                while ((count = stream.read(buffer)) != -1) hash.update(buffer, 0, count);
            }
            if (!HexFormat.of().formatHex(hash.digest()).equals("fe77df10d803e08c95b9d47608444982629d2a426d1f74ac41ec569eb8fe96a8"))
                throw new IllegalStateException("Pinned SerializerDebug binary identity differs");
        } catch (java.io.IOException | java.security.NoSuchAlgorithmException failure) {
            throw new IllegalStateException("Pinned datapack recipient compatibility refused", failure);
        }
    }

    static void requireApplied() {
        if (!applied.get()) throw new IllegalStateException("Exact native SerializerDebug recipient redirect required");
    }

    @Override public void onLoad(String name) {
        if (FMLEnvironment.dist == Dist.DEDICATED_SERVER) requirePinnedInput();
    }
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String target, String mixin) { return FMLEnvironment.dist == Dist.DEDICATED_SERVER; }
    @Override public void acceptTargets(Set<String> mine, Set<String> other) { }
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) { }
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {
        if (!TARGET.equals(target) || !"dev.psa.datapacksync.mixin.SerializerDebugDatapackMixin".equals(mixin)
                || node == null || !TARGET.replace('.', '/').equals(node.name))
            throw new IllegalStateException("Exact datapack sync transformation target required");
        var methods = node.methods.stream().filter(method -> method.name.equals("onPlayerDatapackSync")
            && method.desc.equals(EVENT_DESCRIPTOR) && (method.access & (Opcodes.ACC_STATIC | Opcodes.ACC_NATIVE | Opcodes.ACC_ABSTRACT)) == 0).toList();
        if (methods.size() != 1) throw new IllegalStateException("Unique native datapack sync handler required");
        int redirects = 0, originalSends = 0;
        for (var instruction : methods.get(0).instructions) if (instruction instanceof MethodInsnNode call) {
            if (call.owner.equals(node.name) && call.name.contains("psa$sendToDatapackRecipients")
                    && call.desc.equals(HANDLER_DESCRIPTOR)) redirects++;
            if (call.owner.equals("net/minecraftforge/network/simple/SimpleChannel") && call.name.equals("send")
                    && call.desc.equals(SEND_DESCRIPTOR)) originalSends++;
        }
        long handlers = node.methods.stream().filter(method -> method.name.contains("psa$sendToDatapackRecipients")
            && method.desc.equals(HANDLER_DESCRIPTOR) && (method.access & Opcodes.ACC_PRIVATE) != 0
            && (method.access & (Opcodes.ACC_STATIC | Opcodes.ACC_NATIVE | Opcodes.ACC_ABSTRACT)) == 0).count();
        if (redirects != 1 || originalSends != 0 || handlers != 1)
            throw new IllegalStateException("One completed native recipient redirect required");
        applied.set(true);
    }
}
