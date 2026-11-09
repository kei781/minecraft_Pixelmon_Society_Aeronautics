package dev.psa.compat;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.llamalad7.mixinextras.sugar.Local;
import dev.psa.jademath.JadeCoordinateMath;
import dev.ryanhcode.sable.Sable;
import dev.ryanhcode.sable.sublevel.SubLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Vec3i;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;

/** Keep Jade's threshold and loaded-block guard; measure both integer points in world space. */
@Pseudo
@Mixin(targets = "snownee.jade.impl.BlockAccessorImpl", remap = false)
public abstract class JadeBlockAccessorCoordinatesMixin {
    @WrapOperation(method = "lambda$handleRequest$0", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/core/BlockPos;m_123331_(Lnet/minecraft/core/Vec3i;)D", remap = false),
            require = 1, expect = 1, allow = 1)
    private static double psa$worldDistance(BlockPos block, Vec3i player, Operation<Double> original,
                                           @Local ServerLevel level) {
        SubLevel blockFrame = Sable.HELPER.getContaining(level, block);
        SubLevel playerFrame = Sable.HELPER.getContaining(level, player);
        if (blockFrame == null && playerFrame == null) return original.call(block, player);
        Vec3 blockWorld = JadeCoordinateMath.worldPoint(new Vec3(block.getX(), block.getY(), block.getZ()),
                blockFrame == null ? null : blockFrame.logicalPose());
        Vec3 playerWorld = JadeCoordinateMath.worldPoint(new Vec3(player.getX(), player.getY(), player.getZ()),
                playerFrame == null ? null : playerFrame.logicalPose());
        return blockWorld.distanceToSqr(playerWorld);
    }
}
