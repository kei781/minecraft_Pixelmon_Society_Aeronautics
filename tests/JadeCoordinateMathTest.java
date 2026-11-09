import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import dev.psa.compat.JadeCoordinateMath;
import dev.ryanhcode.sable.companion.math.Pose3d;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaterniond;
import org.joml.Vector3d;

import java.util.Optional;

/** Standalone controls against actual Minecraft AABB and Sable/JOML pose math. */
public final class JadeCoordinateMathTest {
    private static int checks;
    private static final Operation<Optional<Vec3>> CLIP = args ->
            ((AABB) args[0]).clip((Vec3) args[1], (Vec3) args[2]);
    private static final Operation<Boolean> CONTAINS = args ->
            ((AABB) args[0]).contains((Vec3) args[1]);

    private static void check(boolean condition, String label) {
        checks++;
        if (!condition) throw new AssertionError(label);
    }

    private static void near(Vec3 actual, Vec3 expected, String label) {
        check(actual.distanceToSqr(expected) < 1.0E-12, label + ": " + actual + " vs " + expected);
    }

    public static void main(String[] args) {
        Vec3 start = new Vec3(20, 104, 7.5), end = new Vec3(27, 104, 7.5);
        AABB worldBox = new AABB(23, 103, 7, 24, 105, 8);
        check(JadeCoordinateMath.worldPoint(start, null) == start, "world points retain identity");
        Optional<Vec3> vanilla = worldBox.clip(start, end);
        check(JadeCoordinateMath.clip(worldBox, start, end, null, CLIP).equals(vanilla), "world clip exact");
        check(JadeCoordinateMath.contains(worldBox, start, null, CONTAINS) == worldBox.contains(start), "world contains exact");

        // Ship storage is far away; world ray stays short under translation and rotation.
        Vec3 localOrigin = new Vec3(20481037, 100, 20481037);
        for (double angle : new double[] {0, Math.PI / 2, 0.37, -1.19}) {
            Pose3d pose = new Pose3d(new Vector3d(23.5, 104, 7.5),
                    new Quaterniond().rotateY(angle),
                    new Vector3d(localOrigin.x, localOrigin.y, localOrigin.z), new Vector3d(1));
            AABB box = new AABB(localOrigin.x - .5, localOrigin.y - 1, localOrigin.z - .5,
                    localOrigin.x + .5, localOrigin.y + 1, localOrigin.z + .5);
            Vec3 localStart = localOrigin.add(-3.5, 0, 0), localEnd = localOrigin.add(3.5, 0, 0);
            Vec3 worldStart = pose.transformPosition(localStart), worldEnd = pose.transformPosition(localEnd);
            check(!box.clip(worldStart, worldEnd).isPresent(), "baseline mixed-frame miss");
            near(JadeCoordinateMath.clip(box, worldStart, worldEnd, pose, CLIP).orElseThrow(),
                    pose.transformPosition(localOrigin.add(-.5, 0, 0)), "projected clip hit");
            check(JadeCoordinateMath.contains(box, pose.transformPosition(localOrigin), pose, CONTAINS), "camera inside local box");
            check(!JadeCoordinateMath.contains(box, worldStart, pose, CONTAINS), "camera outside local box");
            near(JadeCoordinateMath.worldPoint(localOrigin, pose), new Vec3(23.5, 104, 7.5), "hit projection");
            check(worldStart.distanceTo(localOrigin) > 1_000_000
                    && Math.abs(worldStart.distanceTo(JadeCoordinateMath.worldPoint(localOrigin, pose)) - 3.5) < 1.0E-8,
                    "distance tooltip uses world distance instead of storage magnitude");
            check(new AABB(worldStart, worldEnd).getSize() < 8, "bounded broadphase");
            Vec3 nearHit = JadeCoordinateMath.clip(box, worldStart, worldEnd, pose, CLIP).orElseThrow();
            Vec3 fartherBlock = pose.transformPosition(localOrigin.add(1, 0, 0));
            check(worldStart.distanceToSqr(nearHit) < worldStart.distanceToSqr(fartherBlock), "nearest world-distance ordering");
            Vec3 missEnd = pose.transformPosition(localEnd.add(0, 4, 0));
            check(!JadeCoordinateMath.clip(box, worldStart.add(0, 4, 0), missEnd, pose, CLIP).isPresent(), "native miss remains empty");
        }
        RuntimeException sentinel = new RuntimeException("native clip failure");
        try {
            JadeCoordinateMath.clip(worldBox, start, end, null, ignored -> { throw sentinel; });
            throw new AssertionError("failure swallowed");
        } catch (RuntimeException actual) {
            check(actual == sentinel, "native failure propagates");
        }
        System.out.println("JadeCoordinateMath controls passed: " + checks);
    }
}
