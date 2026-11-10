package dev.psa.datapacksync;

import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLEnvironment;

/** Dedicated-server correction; the original client receiver and protocol remain unchanged. */
@Mod("psadatapacksynccompat")
public final class DatapackSyncCompat {
    public DatapackSyncCompat() throws ClassNotFoundException {
        if (FMLEnvironment.dist != Dist.DEDICATED_SERVER) return;
        DatapackSyncPlugin.requirePinnedInput();
        Class.forName(DatapackSyncPlugin.TARGET);
        DatapackSyncPlugin.requireApplied();
    }
}
