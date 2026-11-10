package dev.psa.alicompat.mixin;

import dev.psa.alicompat.AliPaletteAccess;
import com.yanny.aci.manager.CoreServerRegistry;
import com.yanny.aci.tooltip.TooltipNode;
import com.yanny.aci.tooltip.TooltipNodePalette;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Preserve the native empty factory and use its existing client palette remotely. */
@Mixin(value = TooltipNode.class, remap = false)
public abstract class AliTooltipPaletteMixin {
    @Redirect(method = "empty", at = @At(value = "INVOKE", target =
        "Lcom/yanny/aci/manager/CoreServerRegistry;getTooltipCache()Lcom/yanny/aci/tooltip/TooltipNodePalette;"),
        require = 1, expect = 1, allow = 1, remap = false)
    private static TooltipNodePalette psa$selectExistingPalette(CoreServerRegistry<?, ?, ?> server) {
        return AliPaletteAccess.select(server);
    }
}
