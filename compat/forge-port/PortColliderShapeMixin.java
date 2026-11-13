package dev.psa.portfix.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.mojang.logging.LogUtils;
import dev.ryanhcode.sable.physics.impl.rapier.collider.PhysicsColliderBlockGetter;
import dev.ryanhcode.sable.physics.impl.rapier.collider.RapierVoxelColliderBakery;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import org.slf4j.Logger;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;

/**
 * The port asks every block for its collision shape through a stand-in level that is never told
 * which block it holds, so the block reads null at its own position. Pixelmon's multi-block
 * machines read their own and their base block there; the exception left the block half placed
 * and stopped the server when a physics structure came near one.
 */
@Mixin(value = RapierVoxelColliderBakery.class, remap = false)
public abstract class PortColliderShapeMixin {
    @Unique private static final Logger PSA_LOGGER = LogUtils.getLogger();
    @Unique private static final Set<Block> PSA_REPORTED = ConcurrentHashMap.newKeySet();

    @WrapOperation(method = "buildPhysicsDataForBlock", at = @At(value = "INVOKE", target =
        "Lnet/minecraft/world/level/block/state/BlockState;m_60742_(Lnet/minecraft/world/level/BlockGetter;Lnet/minecraft/core/BlockPos;Lnet/minecraft/world/phys/shapes/CollisionContext;)Lnet/minecraft/world/phys/shapes/VoxelShape;"),
        require = 1, expect = 1, allow = 1, remap = false)
    private VoxelShape psa$shapeOfAnyBlock(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context,
                                           Operation<VoxelShape> original) {
        try {
            if (level instanceof PhysicsColliderBlockGetter standIn) {
                synchronized (standIn) {
                    standIn.setup(state);
                    return original.call(state, level, pos, context);
                }
            }
            return original.call(state, level, pos, context);
        } catch (RuntimeException failure) {
            // The stand-in has air around the block: a block that reads a neighbour (the upper half
            // of a Pixelmon machine reads its base) still fails. It then collides as a full block.
            if (PSA_REPORTED.add(state.getBlock()))
                PSA_LOGGER.warn("PSA: {} gave no collision shape to the physics engine and is treated as a full block", state.getBlock(), failure);
            return Shapes.block();
        }
    }
}
