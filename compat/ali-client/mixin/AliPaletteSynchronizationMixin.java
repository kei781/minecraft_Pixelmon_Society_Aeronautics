package dev.psa.alicompat.mixin;

import com.yanny.aci.tooltip.TooltipNodePalette;
import org.spongepowered.asm.mixin.Mixin;

/** Plugin adds JVM synchronized flags to six exact native palette methods. No body is copied. */
@Mixin(value = TooltipNodePalette.class, remap = false)
public abstract class AliPaletteSynchronizationMixin { }
