package dev.psa.alicompat.mixin;

import com.yanny.aci.manager.CoreServerRegistry;
import com.yanny.aci.tooltip.TooltipBuilder;
import com.yanny.aci.tooltip.TooltipNodePalette;
import dev.psa.alicompat.AliPaletteAccess;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Preserve native nonempty builder data, flags and child nodes. */
@Mixin(value = TooltipBuilder.class, remap = false)
public abstract class AliTooltipBuilderPaletteMixin {
    @Redirect(method = "build()Lcom/yanny/aci/tooltip/TooltipNode;", at = @At(value = "INVOKE", target =
        "Lcom/yanny/aci/manager/CoreServerRegistry;getTooltipCache()Lcom/yanny/aci/tooltip/TooltipNodePalette;"),
        require = 1, expect = 1, allow = 1, remap = false)
    private TooltipNodePalette psa$selectExistingPalette(CoreServerRegistry<?, ?, ?> server) {
        return AliPaletteAccess.select(server);
    }
}
