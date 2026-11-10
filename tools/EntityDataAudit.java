import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.ZipInputStream;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.Type;
import org.objectweb.asm.Handle;
import org.objectweb.asm.ConstantDynamic;
import org.objectweb.asm.tree.*;
import org.objectweb.asm.tree.analysis.*;

/** Offline metadata audit. Never loads any Minecraft or mod class. JSONL on stdout. */
public final class EntityDataAudit {
    private static int classes, registrations, helpers, dynamic, handleReferences;
    private static int classArgument(MethodInsnNode call) {
        if (call.owner.equals("net/minecraft/network/syncher/SynchedEntityData")
                && Set.of("defineId", "m_135353_").contains(call.name)) {
            if (!call.desc.equals("(Ljava/lang/Class;Lnet/minecraft/network/syncher/EntityDataSerializer;)Lnet/minecraft/network/syncher/EntityDataAccessor;"))
                throw new IllegalArgumentException("Unexpected defineId descriptor: " + call.desc);
            return 0;
        }
        // The dynamic allocation helpers discovered in this pinned pack's direct scan.
        if (call.owner.equals("com/pixelmonmod/pixelmon/api/data/DataSync") && call.name.equals("<init>")
                && call.desc.startsWith("(Ljava/lang/Class;Lnet/minecraft/network/syncher/EntityDataSerializer;")) return 0;
        if (call.owner.startsWith("de/markusbordihn/easynpc/entity/easynpc/data/")
                && call.name.startsWith("registerSyn") && call.desc.equals("(Ljava/util/EnumMap;Ljava/lang/Class;)V")) return 1;
        if (call.owner.equals("de/markusbordihn/easynpc/entity/easynpc/EasyNPCBase")
                && call.name.equals("registerEasyNPCSyncedData") && call.desc.equals("(Ljava/util/EnumMap;Ljava/lang/Class;)V")) return 1;
        return -1;
    }
    private static String quote(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
    }
    private static String array(Set<String> values) {
        return "[" + String.join(",", values.stream().map(EntityDataAudit::quote).toList()) + "]";
    }
    private static final class Origins extends SourceInterpreter {
        Origins() { super(Opcodes.ASM9); }
        @Override public SourceValue newParameterValue(boolean instance, int local, Type type) {
            return new SourceValue(type.getSize(), new VarInsnNode(Opcodes.ALOAD, local));
        }
        @Override public SourceValue copyOperation(AbstractInsnNode insn, SourceValue value) { return value; }
        @Override public SourceValue unaryOperation(AbstractInsnNode insn, SourceValue value) {
            return insn.getOpcode() == Opcodes.CHECKCAST ? value : super.unaryOperation(insn, value);
        }
    }
    private static int classParameter(MethodNode method, int local) {
        int slot = (method.access & Opcodes.ACC_STATIC) == 0 ? 1 : 0;
        Type[] types = Type.getArgumentTypes(method.desc);
        for (int i = 0; i < types.length; i++) {
            if (slot == local && types[i].equals(Type.getType(Class.class))) return i;
            slot += types[i].getSize();
        }
        return -1;
    }
    private static void inspectConstant(String artifact, ClassNode node, MethodNode method, Object value) {
        if (value instanceof Handle handle) {
            MethodInsnNode call = new MethodInsnNode(Opcodes.INVOKESTATIC, handle.getOwner(), handle.getName(), handle.getDesc(), handle.isInterface());
            if (classArgument(call) < 0) return;
            handleReferences++;
            System.out.println("{\"jar\":" + quote(artifact) + ",\"class\":" + quote(node.name)
                    + ",\"method\":" + quote(method.name + method.desc) + ",\"owners\":[],\"serializers\":[],"
                    + "\"call_type\":\"HANDLE\",\"kind\":\"DYNAMIC_OWNER\",\"owner_is_forwarded_parameter\":false,"
                    + "\"allocation_api\":" + quote(handle.getOwner() + "#" + handle.getName() + handle.getDesc()) + "}");
        } else if (value instanceof ConstantDynamic constant) {
            inspectConstant(artifact, node, method, constant.getBootstrapMethod());
            for (int i = 0; i < constant.getBootstrapMethodArgumentCount(); i++)
                inspectConstant(artifact, node, method, constant.getBootstrapMethodArgument(i));
        }
    }
    private static Set<String> mixinTargets(ClassNode node) {
        Set<String> result = new LinkedHashSet<>();
        List<AnnotationNode> annotations = new ArrayList<>();
        if (node.visibleAnnotations != null) annotations.addAll(node.visibleAnnotations);
        if (node.invisibleAnnotations != null) annotations.addAll(node.invisibleAnnotations);
        for (AnnotationNode annotation : annotations) {
            if (!annotation.desc.equals("Lorg/spongepowered/asm/mixin/Mixin;") || annotation.values == null) continue;
            for (int i = 0; i < annotation.values.size(); i += 2) {
                if (!Set.of("value", "targets").contains(annotation.values.get(i))) continue;
                Object value = annotation.values.get(i + 1);
                if (!(value instanceof List<?> values)) throw new IllegalArgumentException("Invalid Mixin targets");
                for (Object target : values) result.add(target instanceof Type type ? type.getInternalName() : target.toString().replace('.', '/'));
            }
        }
        return result;
    }
    private static void inspect(String artifact, String entry, byte[] bytes) throws Exception {
        classes++;
        ClassNode node = new ClassNode();
        new org.objectweb.asm.ClassReader(bytes).accept(node, 0);
        Set<String> targets = mixinTargets(node);
        for (MethodNode method : node.methods) {
            for (AbstractInsnNode insn : method.instructions) {
                if (insn instanceof InvokeDynamicInsnNode invocation) {
                    inspectConstant(artifact, node, method, invocation.bsm);
                    for (Object argument : invocation.bsmArgs) inspectConstant(artifact, node, method, argument);
                } else if (insn instanceof LdcInsnNode constant) inspectConstant(artifact, node, method, constant.cst);
            }
            boolean relevant = false;
            for (AbstractInsnNode insn : method.instructions) if (insn instanceof MethodInsnNode call
                    && classArgument(call) >= 0) relevant = true;
            if (!relevant) continue;
            Frame<SourceValue>[] frames = new Analyzer<>(new Origins()).analyze(node.name, method);
            for (int i = 0; i < method.instructions.size(); i++) {
                AbstractInsnNode insn = method.instructions.get(i);
                if (!(insn instanceof MethodInsnNode call)) continue;
                int argument = classArgument(call);
                if (argument < 0) continue;
                boolean direct = call.owner.equals("net/minecraft/network/syncher/SynchedEntityData");
                Frame<SourceValue> frame = frames[i];
                if (frame == null) throw new IllegalArgumentException("Unreachable registration: " + node.name);
                Set<String> owners = new LinkedHashSet<>(), serializers = new LinkedHashSet<>(), parameters = new LinkedHashSet<>();
                boolean incomplete = false;
                boolean forwardedParameter = true;
                int argumentCount = Type.getArgumentTypes(call.desc).length;
                SourceValue owner = frame.getStack(frame.getStackSize() - argumentCount + argument);
                for (AbstractInsnNode source : owner.insns) {
                    if (source instanceof LdcInsnNode constant && constant.cst instanceof Type type) {
                        owners.add(type.getInternalName());
                        forwardedParameter = false;
                    } else {
                        incomplete = true;
                        int parameter = source instanceof VarInsnNode variable ? classParameter(method, variable.var) : -1;
                        if (parameter >= 0) parameters.add(Integer.toString(parameter));
                        else forwardedParameter = false;
                    }
                }
                incomplete |= owner.insns.isEmpty();
                if (direct) for (AbstractInsnNode source : frame.getStack(frame.getStackSize() - 1).insns)
                    serializers.add(source instanceof FieldInsnNode field ? field.owner + "#" + field.name : source.getClass().getSimpleName());
                String kind = incomplete ? "DYNAMIC_OWNER" : owners.size() == 1 && owners.contains(node.name) ? "OWN_CLASS"
                        : !targets.isEmpty() && targets.containsAll(owners) ? "MIXIN_TARGET" : "FOREIGN_OWNER";
                if (direct) registrations++; else helpers++;
                if (incomplete) dynamic++;
                System.out.println("{\"jar\":" + quote(artifact) + ",\"class\":" + quote(node.name)
                        + ",\"method\":" + quote(method.name + method.desc) + ",\"owners\":" + array(owners)
                        + ",\"allocation_api\":" + quote(call.owner + "#" + call.name + call.desc)
                        + ",\"call_type\":" + quote(direct ? "DIRECT" : "HELPER")
                        + ",\"forwarded_class_parameters\":" + array(parameters)
                        + ",\"owner_is_forwarded_parameter\":" + (forwardedParameter && !parameters.isEmpty())
                        + ",\"serializers\":" + array(serializers) + ",\"kind\":" + quote(kind) + "}");
            }
        }
    }
    private static void archive(String artifact, byte[] bytes) throws Exception {
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            java.util.zip.ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                if (entry.getName().endsWith(".class")) inspect(artifact, entry.getName(), zip.readAllBytes());
                else if (entry.getName().startsWith("META-INF/jarjar/") && entry.getName().endsWith(".jar"))
                    archive(artifact + "!" + entry.getName(), zip.readAllBytes());
            }
        }
    }
    public static void main(String[] args) throws Exception {
        if (args.length == 0) throw new IllegalArgumentException("Supply explicit mod JAR paths");
        for (String name : args) archive(Path.of(name).getFileName().toString(), Files.readAllBytes(Path.of(name)));
        System.err.println("classes=" + classes + " direct_registrations=" + registrations + " helper_calls=" + helpers
                + " dynamic_owner_calls=" + dynamic + " allocation_handle_references=" + handleReferences);
    }
}
