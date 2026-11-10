package dev.psa.alicompat;

import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLEnvironment;

/** Client-only correction for the pinned ALI empty-tooltip palette lookup. */
@Mod("psaaliclientcompat")
public final class AliClientCompat {
    public AliClientCompat() {
        if (FMLEnvironment.dist != Dist.CLIENT) throw new IllegalStateException("ALI compatibility is client-only");
        // A plugin exception alone can disable a Mixin config without stopping Forge.
        AliCompatPlugin.requirePinnedInput();
        AliCompatPlugin.requireWrapRuntime();
        try {
            Class.forName(AliCompatPlugin.PALETTE_TARGET);
            Class.forName(AliCompatPlugin.TARGET);
            Class.forName(AliCompatPlugin.BUILDER_TARGET);
            AliCompatPlugin.requireCompletedRegistration(Class.forName(AliCompatPlugin.REGISTRATION_TARGET));
        }
        catch (ClassNotFoundException failure) { throw new IllegalStateException("Pinned ALI target missing", failure); }
        AliCompatPlugin.requireApplied();
    }
}
