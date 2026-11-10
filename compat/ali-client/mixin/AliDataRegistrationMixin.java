package dev.psa.alicompat.mixin;

import com.llamalad7.mixinextras.injector.wrapmethod.WrapMethod;
import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.yanny.aci.manager.CorePluginManager;
import dev.emi.emi.api.EmiRegistry;
import org.spongepowered.asm.mixin.Mixin;

/** Keep one native registration batch on the same palette generation as its decoded data. */
@Mixin(targets = "com.yanny.ali.emi.compatibility.EmiCompatibility", remap = false)
public abstract class AliDataRegistrationMixin {
    @WrapMethod(method = "registerData", remap = false, require = 1, expect = 1, allow = 1)
    private void psa$registerOnePaletteGeneration(EmiRegistry registry, byte[] data, Operation<Void> original) {
        var manager = CorePluginManager.INSTANCE;
        var client = manager == null ? null : manager.clientRegistry;
        var palette = client == null ? null : client.getTooltipCache();
        if (palette == null) { original.call(registry, data); return; }
        synchronized (palette) { original.call(registry, data); }
    }
}
