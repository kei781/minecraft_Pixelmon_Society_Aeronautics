package dev.psa.jademath;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import dev.ryanhcode.sable.companion.math.Pose3dc;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

import java.util.Optional;

/** Ray math uses world distances; a candidate box may live in a ship's storage. */
public final class JadeCoordinateMath {
    private JadeCoordinateMath() {}

    public static Vec3 worldPoint(Vec3 point, Pose3dc pose) {
        return pose == null ? point : pose.transformPosition(point);
    }

    public static boolean contains(AABB box, Vec3 worldPoint, Pose3dc pose,
                                   Operation<Boolean> original) {
        return original.call(box, pose == null ? worldPoint : pose.transformPositionInverse(worldPoint));
    }

    public static Optional<Vec3> clip(AABB box, Vec3 worldStart, Vec3 worldEnd, Pose3dc pose,
                                     Operation<Optional<Vec3>> original) {
        if (pose == null) return original.call(box, worldStart, worldEnd);
        Optional<Vec3> localHit = original.call(box, pose.transformPositionInverse(worldStart),
                pose.transformPositionInverse(worldEnd));
        return localHit.map(pose::transformPosition);
    }
}
