package dev.psa.jadeprobe;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import java.util.function.Predicate;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

@Mixin(targets = "snownee.jade.overlay.RayTracing", remap = false)
public abstract class JadeQueryProbeMixin {
    @WrapOperation(method = "rayTrace", at = @At(value = "INVOKE",
            target = "Lsnownee/jade/overlay/RayTracing;getEntityHitResult(Lnet/minecraft/world/level/Level;Lnet/minecraft/world/entity/Entity;Lnet/minecraft/world/phys/Vec3;Lnet/minecraft/world/phys/Vec3;Lnet/minecraft/world/phys/AABB;Ljava/util/function/Predicate;)Lnet/minecraft/world/phys/EntityHitResult;", remap = false),
            require = 1, expect = 1, allow = 1)
    private EntityHitResult psa$observeActualQuery(Level level, Entity viewer, Vec3 start, Vec3 end,
                                                  AABB bounds, Predicate<Entity> predicate,
                                                  Operation<EntityHitResult> original) {
        EntityHitResult result = original.call(level, viewer, start, end, bounds, predicate);
        JadeProbe.returned(start, end, bounds);
        return result;
    }
}
