package dev.psa.alicompat;

/** Runs only the compiled identity/latch guards, never a game or a fake ALI binary. */
public final class AliCompatGateProbe {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("valid, refuse or unapplied required");
        switch (args[0]) {
            case "valid" -> AliCompatPlugin.requirePinnedInput();
            case "refuse" -> {
                try { AliCompatPlugin.requirePinnedInput(); }
                catch (IllegalStateException expected) { System.out.println("PINNED_INPUT_REFUSED"); return; }
                throw new AssertionError("Invalid input accepted");
            }
            case "unapplied" -> {
                try { AliCompatPlugin.requireApplied(); }
                catch (IllegalStateException expected) { System.out.println("UNAPPLIED_TRANSFORM_REFUSED"); return; }
                throw new AssertionError("Missing transform accepted");
            }
            case "partial-node", "partial-builder" -> {
                var plugin = new AliCompatPlugin();
                if (args[0].equals("partial-node"))
                    plugin.postApply(AliCompatPlugin.TARGET, null, "dev.psa.alicompat.mixin.AliTooltipPaletteMixin", null);
                else plugin.postApply(AliCompatPlugin.BUILDER_TARGET, null, "dev.psa.alicompat.mixin.AliTooltipBuilderPaletteMixin", null);
                try { AliCompatPlugin.requireApplied(); }
                catch (IllegalStateException expected) { System.out.println("PARTIAL_TRANSFORM_REFUSED"); return; }
                throw new AssertionError("Partial transform accepted");
            }
            case "partial-factories" -> {
                var plugin = new AliCompatPlugin();
                plugin.postApply(AliCompatPlugin.TARGET, null, "dev.psa.alicompat.mixin.AliTooltipPaletteMixin", null);
                plugin.postApply(AliCompatPlugin.BUILDER_TARGET, null, "dev.psa.alicompat.mixin.AliTooltipBuilderPaletteMixin", null);
                try { AliCompatPlugin.requireApplied(); }
                catch (IllegalStateException expected) { System.out.println("MISSING_PALETTE_LOCK_REFUSED"); return; }
                throw new AssertionError("Missing palette locking accepted");
            }
            case "missing-registration", "palette-missing-method", "palette-static-method", "all-callbacks" -> {
                AliCompatPlugin.requirePinnedInput();
                var node = new org.objectweb.asm.tree.ClassNode();
                try (var jar = new java.util.zip.ZipFile("mods/AdvancedLootInfo-forge-1.20.1-1.12.0.jar")) {
                    new org.objectweb.asm.ClassReader(jar.getInputStream(jar.getEntry(
                        "com/yanny/aci/tooltip/TooltipNodePalette.class"))).accept(node, 0);
                }
                if (args[0].equals("palette-missing-method")) node.methods.removeIf(method -> method.name.equals("clear"));
                if (args[0].equals("palette-static-method")) node.methods.stream().filter(method -> method.name.equals("clear"))
                    .forEach(method -> method.access |= org.objectweb.asm.Opcodes.ACC_STATIC);
                var plugin = new AliCompatPlugin();
                try {
                    plugin.postApply(AliCompatPlugin.PALETTE_TARGET, node, "dev.psa.alicompat.mixin.AliPaletteSynchronizationMixin", null);
                } catch (IllegalStateException expected) {
                    if (!args[0].startsWith("palette-")) throw expected;
                    System.out.println("UNEXPECTED_PALETTE_SHAPE_REFUSED"); return;
                }
                if (args[0].startsWith("palette-")) throw new AssertionError("Unexpected palette shape accepted");
                long guarded = node.methods.stream().filter(method -> java.util.Set.of(
                    "getOrCreate", "getNodeId", "getNodeById", "encode", "decode", "clear").contains(method.name))
                    .filter(method -> (method.access & org.objectweb.asm.Opcodes.ACC_SYNCHRONIZED) != 0).count();
                if (guarded != 6) throw new AssertionError("Six native methods must acquire the palette monitor");
                plugin.postApply(AliCompatPlugin.TARGET, null, "dev.psa.alicompat.mixin.AliTooltipPaletteMixin", null);
                plugin.postApply(AliCompatPlugin.BUILDER_TARGET, null, "dev.psa.alicompat.mixin.AliTooltipBuilderPaletteMixin", null);
                if (args[0].equals("missing-registration")) {
                    try { AliCompatPlugin.requireApplied(); }
                    catch (IllegalStateException expected) { System.out.println("MISSING_REGISTRATION_WRAP_REFUSED"); return; }
                    throw new AssertionError("Missing batch wrapper accepted");
                }
                plugin.postApply(AliCompatPlugin.REGISTRATION_TARGET, null, "dev.psa.alicompat.mixin.AliDataRegistrationMixin", null);
                AliCompatPlugin.requireApplied(); System.out.println("ALL_CALLBACKS_ACCEPTED_SIX_MONITORS"); return;
            }
            default -> throw new IllegalArgumentException("Known guard case required");
        }
        System.out.println("PINNED_INPUT_ACCEPTED");
    }
}
