package dev.psa.alicompat;

import com.yanny.aci.manager.CorePluginManager;
import com.yanny.aci.manager.CoreServerRegistry;
import com.yanny.aci.tooltip.TooltipNodePalette;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLEnvironment;

/** Select an existing native registry; no new palettes or synthetic tooltip nodes. */
public final class AliPaletteAccess {
    private AliPaletteAccess() { }
    public static TooltipNodePalette select(CoreServerRegistry<?, ?, ?> server) {
        if (server == null && FMLEnvironment.dist == Dist.CLIENT) {
            var client = CorePluginManager.INSTANCE.clientRegistry;
            if (client != null) return client.getTooltipCache();
        }
        return server.getTooltipCache();
    }
}
