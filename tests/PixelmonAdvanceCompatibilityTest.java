package dev.psa.pixelmonrender;

import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** Uses the actual pinned Embeddium class as the positive reference. */
public final class PixelmonAdvanceCompatibilityTest {
    private static ClassNode reference() throws Exception {
        String resource="/me/jellysquid/mods/sodium/mixin/features/render/immediate/buffer_builder/BufferBuilderMixin.class";
        ClassNode node=new ClassNode();
        try(var input=PixelmonAdvanceCompatibilityTest.class.getResourceAsStream(resource)) {
            if(input==null)throw new AssertionError("Pinned Embeddium reference missing");
            new ClassReader(input).accept(node,0);
        }
        return node;
    }
    private static MethodNode next(ClassNode node) {
        return node.methods.stream().filter(m->m.name.equals("m_5751_")&&m.desc.equals("()V")).findFirst().orElseThrow();
    }
    private static MethodNode authored(ClassNode node) {
        MethodNode method=new MethodNode(Opcodes.ACC_PUBLIC,"psa$tryAdvanceEntityBase","()Z",null,null);
        method.instructions.add(new InsnNode(Opcodes.ICONST_1));
        method.instructions.add(new InsnNode(Opcodes.IRETURN));
        node.methods.add(method); return method;
    }
    public static void main(String[] args) throws Exception {
        ClassNode valid=reference();
        if(!AdvanceCompatibility.supports(valid))throw new AssertionError("Pinned Embeddium method rejected");
        MethodNode retained=authored(valid);
        AdvanceCompatibility.disableUnsupported(valid);
        if(retained.instructions.getFirst().getOpcode()!=Opcodes.ICONST_1)
            throw new AssertionError("Supported bypass was disabled");

        ClassNode hooked=reference();
        next(hooked).instructions.insert(new MethodInsnNode(Opcodes.INVOKESTATIC,"other/Hook","next","()V",false));
        MethodNode disabled=authored(hooked);
        if(AdvanceCompatibility.supports(hooked))throw new AssertionError("Foreign nextElement hook accepted");
        AdvanceCompatibility.disableUnsupported(hooked);
        if(disabled.instructions.size()!=2 || disabled.instructions.getFirst().getOpcode()!=Opcodes.ICONST_0
                || disabled.instructions.getLast().getOpcode()!=Opcodes.IRETURN)
            throw new AssertionError("Unexpected method must fall back without state mutation");

        ClassNode changed=reference();
        for(AbstractInsnNode instruction:next(changed).instructions) if(instruction instanceof FieldInsnNode field) {
            field.name="changed";break;
        }
        if(AdvanceCompatibility.supports(changed))throw new AssertionError("Changed cursor semantics accepted");
        ClassNode missing=reference();missing.methods.remove(next(missing));
        if(AdvanceCompatibility.supports(missing))throw new AssertionError("Missing nextElement accepted");
        ClassNode duplicate=reference();duplicate.methods.add(next(duplicate));
        if(AdvanceCompatibility.supports(duplicate))throw new AssertionError("Ambiguous nextElement accepted");
        System.out.println("PASS real Embeddium method and unsupported-hook/body/missing/ambiguous rejection");
    }
}
