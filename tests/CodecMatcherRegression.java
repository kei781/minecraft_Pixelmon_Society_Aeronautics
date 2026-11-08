import java.lang.reflect.Method;
import net.minecraft.util.StringRepresentable;

/** Regression for the actual ArrayStoreException found during the second boot. */
public class CodecMatcherRegression {
    enum NonComponentKind implements StringRepresentable {
        EXAMPLE;
        public String getSerializedName() { return "example"; }
    }

    public static void main(String[] args) throws Exception {
        Class<?> patch = Class.forName("team.creative.creativecore.mixin.ComponentSerializationMixin");
        Method hook = patch.getDeclaredMethod("psa$addItemStackType", StringRepresentable[].class);
        hook.setAccessible(true);
        NonComponentKind[] original = { NonComponentKind.EXAMPLE };
        Object result = hook.invoke(null, (Object) original);
        if (result != original) {
            throw new AssertionError("Non-component codec tables must be returned unchanged");
        }
        NonComponentKind[] empty = {};
        if (hook.invoke(null, (Object) empty) != empty) {
            throw new AssertionError("Empty non-component tables must be returned unchanged");
        }
        System.out.println("PASS: other generic codec matcher callers remain unchanged");
    }
}
