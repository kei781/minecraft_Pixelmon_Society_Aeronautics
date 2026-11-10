package dev.psa.alicompat;

/** Runs only the compiled identity/latch guards, never a game or a fake ALI binary. */
public final class AliCompatGateProbe {
    public static void main(String[] args) {
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
            default -> throw new IllegalArgumentException("Known guard case required");
        }
        System.out.println("PINNED_INPUT_ACCEPTED");
    }
}
