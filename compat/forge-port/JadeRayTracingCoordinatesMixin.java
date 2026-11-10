package dev.psa.compat;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import com.llamalad7.mixinextras.injector.wrapmethod.WrapMethod;
import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.llamalad7.mixinextras.sugar.Local;
import dev.psa.jademath.JadeCoordinateMath;
import dev.ryanhcode.sable.Sable;
import dev.ryanhcode.sable.companion.math.Pose3dc;
import dev.ryanhcode.sable.mixinterface.clip_overwrite.LevelPoseProviderExtension;
import dev.ryanhcode.sable.sublevel.ClientSubLevel;
import dev.ryanhcode.sable.sublevel.SubLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;

import java.util.Optional;

/** Optional, pinned Jade11.13.2 adapter. Returned native targets are never rewritten. */
@Pseudo
@Mixin(targets = "snownee.jade.overlay.RayTracing", remap = false)
public abstract class JadeRayTracingCoordinatesMixin {
    @WrapMethod(method = "rayTrace")
    private HitResult psa$renderPoseScope(Entity viewer, double distance, Operation<HitResult> original) {
        Level level = viewer.level();
        if (!(level instanceof LevelPoseProviderExtension provider)) return original.call(viewer, distance);
        // Jade starts from the main camera and the cached render pick, not a server-tick ray.
        provider.sable$pushPoseSupplier(key -> {
            SubLevel frame = (SubLevel) key; // fastutil Function.get takes Object even with a typed key.
            return frame instanceof ClientSubLevel client ? client.renderPose() : frame.logicalPose();
        });
        try {
            return original.call(viewer, distance);
        } finally {
            provider.sable$popPoseSupplier();
        }
    }

    @ModifyExpressionValue(method = "rayTrace", at = {
            @At(value = "INVOKE", target = "Lnet/minecraft/world/phys/HitResult;m_82450_()Lnet/minecraft/world/phys/Vec3;", remap = false),
            @At(value = "INVOKE", target = "Lnet/minecraft/world/phys/EntityHitResult;m_82450_()Lnet/minecraft/world/phys/Vec3;", remap = false),
            @At(value = "INVOKE", target = "Lnet/minecraft/world/phys/BlockHitResult;m_82450_()Lnet/minecraft/world/phys/Vec3;", remap = false)
    }, require = 5, expect = 5, allow = 5)
    private Vec3 psa$worldHitLocation(Vec3 hit, Entity viewer, double distance) {
        return JadeCoordinateMath.worldPoint(hit, psa$poseAt(viewer.level(), hit));
    }

    @WrapOperation(method = "getEntityHitResult", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/phys/AABB;m_82390_(Lnet/minecraft/world/phys/Vec3;)Z", remap = false),
            require = 1, expect = 1, allow = 1)
    private static boolean psa$containsInBoxSpace(AABB box, Vec3 point, Operation<Boolean> original,
                                                 @Local(argsOnly = true) Level level) {
        return JadeCoordinateMath.contains(box, point, psa$poseAt(level, box.getCenter()), original);
    }

    @WrapOperation(method = "getEntityHitResult", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/phys/AABB;m_82371_(Lnet/minecraft/world/phys/Vec3;Lnet/minecraft/world/phys/Vec3;)Ljava/util/Optional;", remap = false),
            require = 1, expect = 1, allow = 1)
    private static Optional<Vec3> psa$clipInBoxSpace(AABB box, Vec3 start, Vec3 end,
                                                   Operation<Optional<Vec3>> original,
                                                   @Local(argsOnly = true) Level level) {
        return JadeCoordinateMath.clip(box, start, end, psa$poseAt(level, box.getCenter()), original);
    }

    @Unique
    private static Pose3dc psa$poseAt(Level level, Vec3 point) {
        SubLevel frame = Sable.HELPER.getContaining(level, point);
        if (frame == null) return null;
        return level instanceof LevelPoseProviderExtension provider
                ? provider.sable$getPose(frame) : frame.logicalPose();
    }
}
