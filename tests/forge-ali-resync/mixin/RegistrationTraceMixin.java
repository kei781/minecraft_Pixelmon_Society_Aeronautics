package dev.psa.aliresync.mixin;

import dev.emi.emi.api.EmiRegistry;
import dev.psa.aliresync.TraceState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets = "com.yanny.ali.emi.compatibility.EmiCompatibility", remap = false)
public abstract class RegistrationTraceMixin {
    @Inject(method = "registerData", at = @At("HEAD"), require = 1, expect = 1, allow = 1, remap = false)
    private void psa$registrationBegin(EmiRegistry registry, byte[] data, CallbackInfo callback) {
        TraceState.beginRegistration();
    }
    @Inject(method = "registerData", at = @At("RETURN"), require = 1, expect = 1, allow = 1, remap = false)
    private void psa$registrationEnd(EmiRegistry registry, byte[] data, CallbackInfo callback) {
        TraceState.endRegistration();
    }
}
