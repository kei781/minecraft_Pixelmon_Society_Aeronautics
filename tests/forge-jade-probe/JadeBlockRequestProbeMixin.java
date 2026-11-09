package dev.psa.jadeprobe;

import com.llamalad7.mixinextras.injector.wrapmethod.WrapMethod;
import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import java.util.function.Consumer;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import org.spongepowered.asm.mixin.Mixin;
import snownee.jade.api.BlockAccessor;

@Mixin(targets = "snownee.jade.impl.BlockAccessorImpl", remap = false)
public abstract class JadeBlockRequestProbeMixin {
    @WrapMethod(method = "lambda$handleRequest$0")
    private static void psa$observe(BlockAccessor accessor, ServerPlayer player,
                                    Consumer<CompoundTag> callback, Operation<Void> original) {
        boolean storageLike = accessor.getPosition().distSqr(player.blockPosition()) > 10000;
        JadeServerRequests.began(true, storageLike);
        Consumer<CompoundTag> forwarded = data -> {
            callback.accept(data);
            JadeServerRequests.callbackReturned(true, storageLike);
        };
        original.call(accessor, player, forwarded);
    }
}
