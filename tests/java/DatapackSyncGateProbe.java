package dev.psa.datapacksync;

import java.nio.file.Path;
import java.util.zip.ZipFile;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.MethodInsnNode;
import org.objectweb.asm.tree.MethodNode;

/** Guard/instruction-metadata fixtures only. Never defines or executes a modified upstream class. */
public final class DatapackSyncGateProbe {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Closed guard case required");
        String mode = args[0];
        if (mode.equals("valid")) { DatapackSyncPlugin.requirePinnedDirectory(Path.of("")); System.out.println("PINNED_INPUT_ACCEPTED"); return; }
        if (mode.equals("refuse")) {
            try { DatapackSyncPlugin.requirePinnedDirectory(Path.of("")); }
            catch (IllegalStateException expected) { System.out.println("INVALID_PINNED_INPUT_REFUSED"); return; }
            throw new AssertionError("Invalid pinned input accepted");
        }
        if (mode.equals("unapplied")) {
            try { DatapackSyncPlugin.requireApplied(); }
            catch (IllegalStateException expected) { System.out.println("UNAPPLIED_REDIRECT_REFUSED"); return; }
            throw new AssertionError("Unapplied redirect accepted");
        }
        if (!java.util.Set.of("wrong-target", "original", "merged-only", "missing-handler", "extra-send",
                "wrong-descriptor", "static-native", "completed-metadata").contains(mode))
            throw new IllegalArgumentException("Known shape case required");
        DatapackSyncPlugin.requirePinnedDirectory(Path.of(""));
        var node = new ClassNode();
        try (var jar = new ZipFile("mods/serializer_debug-1.0.1.jar")) {
            new ClassReader(jar.getInputStream(jar.getEntry("com/dairymoose/sd/SerializerDebugCommon.class"))).accept(node, 0);
        }
        var original = node.methods.stream().filter(method -> method.name.equals("onPlayerDatapackSync")
            && method.desc.equals(DatapackSyncPlugin.EVENT_DESCRIPTOR)).findFirst().orElseThrow();
        if (!java.util.Set.of("wrong-target", "original", "merged-only").contains(mode)) {
            int count = 0;
            for (var instruction : original.instructions) if (instruction instanceof MethodInsnNode call
                    && call.owner.equals("net/minecraftforge/network/simple/SimpleChannel")
                    && call.name.equals("send") && call.desc.equals(DatapackSyncPlugin.SEND_DESCRIPTOR)) {
                call.owner = node.name; call.name = "psa$sendToDatapackRecipients";
                call.desc = mode.equals("wrong-descriptor") ? "(Ljava/lang/Object;)V" : DatapackSyncPlugin.HANDLER_DESCRIPTOR;
                call.setOpcode(Opcodes.INVOKESPECIAL); count++;
            }
            if (count != 1) throw new AssertionError("Exactly one original pinned send site required");
        }
        if (!java.util.Set.of("wrong-target", "original", "missing-handler").contains(mode))
            node.methods.add(new MethodNode(Opcodes.ACC_PRIVATE, "psa$sendToDatapackRecipients",
                DatapackSyncPlugin.HANDLER_DESCRIPTOR, null, null));
        if (mode.equals("extra-send")) original.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL,
            "net/minecraftforge/network/simple/SimpleChannel", "send", DatapackSyncPlugin.SEND_DESCRIPTOR, false));
        if (mode.equals("static-native")) original.access |= Opcodes.ACC_STATIC;
        try {
            new DatapackSyncPlugin().postApply(mode.equals("wrong-target") ? "example.Wrong" : DatapackSyncPlugin.TARGET,
                node, "dev.psa.datapacksync.mixin.SerializerDebugDatapackMixin", null);
        } catch (IllegalStateException expected) {
            if (mode.equals("completed-metadata")) throw expected;
            System.out.println("INVALID_REDIRECT_METADATA_REFUSED"); return;
        }
        if (!mode.equals("completed-metadata")) throw new AssertionError("Invalid redirect metadata accepted");
        DatapackSyncPlugin.requireApplied();
        System.out.println("COMPLETED_REDIRECT_METADATA_ACCEPTED_NOT_GAME_EXECUTION");
    }
}
