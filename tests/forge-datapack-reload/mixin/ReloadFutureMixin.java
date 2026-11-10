package dev.psa.datapackreloadqa.mixin;

import dev.psa.datapackreloadqa.ReloadQaState;
import java.util.Collection;
import java.util.concurrent.CompletableFuture;
import net.minecraft.server.MinecraftServer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "net.minecraft.server.MinecraftServer", remap = false)
public abstract class ReloadFutureMixin {
    @Inject(method = "m_129861_(Ljava/util/Collection;)Ljava/util/concurrent/CompletableFuture;",
        at = @At("RETURN"), remap = false, require = 1, expect = 1, allow = 1)
    private void psa$recordReloadFuture(Collection<String> packs, CallbackInfoReturnable<CompletableFuture<Void>> callback) {
        ReloadQaState.observe((MinecraftServer) (Object) this, callback.getReturnValue());
    }
}
