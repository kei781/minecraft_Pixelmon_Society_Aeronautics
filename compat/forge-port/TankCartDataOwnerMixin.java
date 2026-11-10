package dev.psa.compat;

import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** The pinned TankCart registers its fluid key against the unrelated FlagCart. */
@Pseudo
@Mixin(targets = "com.alc.moreminecarts.entities.TankCartEntity", remap = false)
public abstract class TankCartDataOwnerMixin {
    @ModifyArg(method = "<clinit>", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/network/syncher/SynchedEntityData;m_135353_(Ljava/lang/Class;Lnet/minecraft/network/syncher/EntityDataSerializer;)Lnet/minecraft/network/syncher/EntityDataAccessor;",
            remap = false), index = 0, require = 1, expect = 1, allow = 1)
    private static Class<? extends Entity> psa$useTankCartOwner(Class<? extends Entity> originalOwner)
            throws ClassNotFoundException {
        return Class.forName("com.alc.moreminecarts.entities.TankCartEntity").asSubclass(Entity.class);
    }
}
