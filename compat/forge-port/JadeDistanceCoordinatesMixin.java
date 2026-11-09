package dev.psa.compat;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import dev.ryanhcode.sable.Sable;
import dev.ryanhcode.sable.sublevel.ClientSubLevel;
import dev.ryanhcode.sable.sublevel.SubLevel;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;

/** The optional distance tooltip consumes the original local hit preserved by ray tracing. */
@Pseudo
@Mixin(targets = "snownee.jade.addon.core.DistanceProvider", remap = false)
public abstract class JadeDistanceCoordinatesMixin {
    @WrapOperation(method = "distance", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/phys/Vec3;m_82554_(Lnet/minecraft/world/phys/Vec3;)D", remap = false),
            require = 1, expect = 1, allow = 1)
    private static double psa$worldDistance(Vec3 eye, Vec3 hit, Operation<Double> original) {
        ClientLevel level = Minecraft.getInstance().level;
        if (level == null) return original.call(eye, hit);
        return original.call(psa$renderWorldPoint(level, eye), psa$renderWorldPoint(level, hit));
    }

    @Unique
    private static Vec3 psa$renderWorldPoint(ClientLevel level, Vec3 point) {
        SubLevel frame = Sable.HELPER.getContaining(level, point);
        if (frame == null) return point;
        return JadeCoordinateMath.worldPoint(point, frame instanceof ClientSubLevel client
                ? client.renderPose() : frame.logicalPose());
    }
}
