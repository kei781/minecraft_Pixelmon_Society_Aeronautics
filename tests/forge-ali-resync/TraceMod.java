package dev.psa.aliresync;

import java.lang.reflect.Modifier;
import java.util.Set;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLEnvironment;

@Mod("psaaliresynctrace")
public final class TraceMod {
    public TraceMod() throws ClassNotFoundException {
        TracePlugin.requireOwned();
        Class<?> palette = Class.forName(TracePlugin.TARGET);
        if (FMLEnvironment.dist == Dist.CLIENT) {
            Class.forName("com.yanny.ali.emi.compatibility.EmiCompatibility");
            Set<String> required = Set.of("decode", "encode", "clear", "getOrCreate", "getNodeById", "getNodeId");
            var found = new java.util.HashSet<String>();
            for (var method : palette.getDeclaredMethods()) if (required.contains(method.getName())) {
                if (!Modifier.isSynchronized(method.getModifiers())) throw new IllegalStateException("Actual client palette method lock missing");
                found.add(method.getName());
            }
            if (!found.equals(required)) throw new IllegalStateException("All actual client palette locks required");
        }
        TracePlugin.requireApplied();
    }
}
