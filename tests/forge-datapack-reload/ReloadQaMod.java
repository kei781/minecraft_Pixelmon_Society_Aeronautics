package dev.psa.datapackreloadqa;

import net.minecraftforge.fml.common.Mod;

@Mod("psadatapackreloadqa")
public final class ReloadQaMod {
    public ReloadQaMod() throws ClassNotFoundException {
        ReloadQaPlugin.requireOwned();
        Class.forName(ReloadQaPlugin.TARGET, false, ReloadQaMod.class.getClassLoader());
        ReloadQaPlugin.requireApplied();
    }
}
