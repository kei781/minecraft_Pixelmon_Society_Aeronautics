package dev.psa.aliresync.mixin;

import com.yanny.aci.api.ICoreClientUtils;
import com.yanny.aci.api.ICoreServerUtils;
import com.yanny.aci.tooltip.CacheKey;
import com.yanny.aci.tooltip.TooltipNode;
import com.yanny.aci.tooltip.TooltipNodePalette;
import dev.psa.aliresync.TraceState;
import net.minecraft.network.FriendlyByteBuf;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(value = TooltipNodePalette.class, remap = false)
public abstract class PaletteTraceMixin {
    @Inject(method = "decode", at = @At("HEAD"), require = 1, expect = 1, allow = 1, remap = false)
    private void psa$decodeBegin(ICoreClientUtils<?, ?, ?> utils, FriendlyByteBuf buffer, CallbackInfo callback) {
        TraceState.beginDecode((TooltipNodePalette) (Object) this);
    }
    @Inject(method = "decode", at = @At("RETURN"), require = 1, expect = 1, allow = 1, remap = false)
    private void psa$decodeEnd(ICoreClientUtils<?, ?, ?> utils, FriendlyByteBuf buffer, CallbackInfo callback) {
        TraceState.endDecode((TooltipNodePalette) (Object) this);
    }
    @Inject(method = "encode", at = @At("HEAD"), require = 1, expect = 1, allow = 1, remap = false)
    private void psa$encode(ICoreServerUtils<?> utils, FriendlyByteBuf buffer, CallbackInfo callback) {
        TraceState.beforeEncode((TooltipNodePalette) (Object) this);
    }
    @Inject(method = "getOrCreate", at = @At("HEAD"), require = 1, expect = 1, allow = 1, remap = false)
    private void psa$createBegin(CacheKey key, CallbackInfoReturnable<TooltipNode> callback) {
        TraceState.beginCreate((TooltipNodePalette) (Object) this);
    }
    @Inject(method = "getOrCreate", at = @At("RETURN"), require = 2, expect = 2, allow = 2, remap = false)
    private void psa$createEnd(CacheKey key, CallbackInfoReturnable<TooltipNode> callback) {
        TraceState.endCreate((TooltipNodePalette) (Object) this);
    }
}
