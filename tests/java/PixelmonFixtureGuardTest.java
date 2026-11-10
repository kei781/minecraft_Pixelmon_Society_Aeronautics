package dev.psa.pixelmonfixture;

/** Runs the real preflight in separate fresh working directories/JVMs. */
public final class PixelmonFixtureGuardTest {
    public static void main(String[] args) {
        try {
            FixtureMixinPlugin.requireOwnedProfile();
            throw new AssertionError("Invalid fixture profile unexpectedly accepted");
        } catch (IllegalStateException expected) {
            String wanted = args[0];
            Throwable cause = expected;
            while (cause != null && !cause.toString().contains(wanted)) cause = cause.getCause();
            if (cause == null) throw new AssertionError("Wrong refusal reason", expected);
            System.out.println("PASS real fixture preflight refused: " + wanted);
        }
    }
}
