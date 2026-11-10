import java.nio.file.Files;
import java.nio.file.Path;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;
import org.objectweb.asm.*;

/** Generate never-loaded bytecode with method-reference and literal-Handle blindspot controls. */
public final class AllocationHandleFixture {
    public static void main(String[] args) throws Exception {
        ClassWriter writer = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        writer.visit(Opcodes.V17, Opcodes.ACC_PUBLIC, "psa/fixtures/AllocationReferences", null, "java/lang/Object", null);
        MethodVisitor method = writer.visitMethod(Opcodes.ACC_PUBLIC | Opcodes.ACC_STATIC, "references", "()V", null, null);
        method.visitCode();
        Handle target = new Handle(Opcodes.H_INVOKESTATIC, "net/minecraft/network/syncher/SynchedEntityData", "m_135353_",
                "(Ljava/lang/Class;Lnet/minecraft/network/syncher/EntityDataSerializer;)Lnet/minecraft/network/syncher/EntityDataAccessor;", false);
        Handle bootstrap = new Handle(Opcodes.H_INVOKESTATIC, "java/lang/invoke/LambdaMetafactory", "metafactory",
                "(Ljava/lang/invoke/MethodHandles$Lookup;Ljava/lang/String;Ljava/lang/invoke/MethodType;Ljava/lang/invoke/MethodType;Ljava/lang/invoke/MethodHandle;Ljava/lang/invoke/MethodType;)Ljava/lang/invoke/CallSite;", false);
        method.visitInvokeDynamicInsn("apply", "()Ljava/util/function/BiFunction;", bootstrap,
                Type.getMethodType("(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;"), target, Type.getMethodType(target.getDesc()));
        method.visitInsn(Opcodes.POP);
        method.visitLdcInsn(target);
        method.visitInsn(Opcodes.POP);
        method.visitInsn(Opcodes.RETURN);
        method.visitMaxs(0, 0);
        method.visitEnd();
        writer.visitEnd();
        try (JarOutputStream jar = new JarOutputStream(Files.newOutputStream(Path.of(args[0])))) {
            jar.putNextEntry(new JarEntry("psa/fixtures/AllocationReferences.class"));
            jar.write(writer.toByteArray());
            jar.closeEntry();
        }
    }
}
