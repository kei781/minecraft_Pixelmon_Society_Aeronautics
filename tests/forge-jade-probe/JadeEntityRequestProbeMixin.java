package dev.psa.jadeprobe;

import com.llamalad7.mixinextras.injector.wrapmethod.WrapMethod;
import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import java.util.function.Consumer;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import snownee.jade.api.EntityAccessor;

@Mixin(targets = "snownee.jade.impl.EntityAccessorImpl", remap = false)
public abstract class JadeEntityRequestProbeMixin {
    @WrapMethod(method = "lambda$handleRequest$0")
    private static void psa$observe(EntityAccessor accessor, ServerPlayer player,
                                    Consumer<CompoundTag> callback, Operation<Void> original) {
        Entity entity = accessor.getEntity();
        boolean storageLike = entity != null && player.position().distanceToSqr(entity.position()) > 10000;
        JadeServerRequests.began(false, storageLike);
        Consumer<CompoundTag> forwarded = data -> {
            callback.accept(data);
            JadeServerRequests.callbackReturned(false, storageLike);
        };
        original.call(accessor, player, forwarded);
    }
}
