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
    private static ClassNode writer() throws Exception {
        ClassNode node=new ClassNode();
        try(var input=PixelmonAdvanceCompatibilityTest.class.getResourceAsStream(
                "/dev/psa/pixelmonrender/mixin/EntityBufferMixin.class")) {
            if(input==null)throw new AssertionError("Authored writer missing");
            new ClassReader(input).accept(node,0);
        }
        authored(node);return node;
    }
    private static MethodNode sink(ClassNode node) {
        return node.methods.stream().filter(m->m.name.equals("psa$tryEntityVertex")).findFirst().orElseThrow();
    }
    private static ClassNode mergedWriter() throws Exception {
        ClassNode writer=writer(),reference=reference();MethodNode body=next(reference);
        for(AbstractInsnNode instruction:body.instructions) {
            if(instruction instanceof FieldInsnNode field && field.owner.equals(reference.name))field.owner=writer.name;
            if(instruction instanceof MethodInsnNode call && call.owner.equals(reference.name))call.owner=writer.name;
        }
        writer.methods.removeIf(m->m.name.equals("m_5751_")&&m.desc.equals("()V"));
        writer.methods.add(body);return writer;
    }
    private static int dispatchCalls(MethodNode method) {
        int count=0;
        for(AbstractInsnNode instruction:method.instructions)
            if(instruction instanceof MethodInsnNode call && call.name.equals("psa$tryAdvanceEntityBase"))count++;
        return count;
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
        ClassNode writer=writer();MethodNode sink=sink(writer);int size=sink.instructions.size();
        AbstractInsnNode[] retainedInstructions=sink.instructions.toArray();
        if(!AdvanceCompatibility.installDispatch(writer) || dispatchCalls(sink)!=1)
            throw new AssertionError("Supported writer must dispatch to bulk advance exactly once");
        if(sink.instructions.size()!=size+3)throw new AssertionError("Only three dispatch instructions may be inserted");
        AbstractInsnNode current=sink.instructions.getFirst();
        for(AbstractInsnNode retainedInstruction:retainedInstructions) {
            while(current!=null && current!=retainedInstruction)current=current.getNext();
            if(current==null)throw new AssertionError("Original writer instructions changed order or were removed");
            current=current.getNext();
        }
        ClassNode changedLoop=writer();MethodNode changedSink=sink(changedLoop);
        for(AbstractInsnNode instruction:changedSink.instructions)if(instruction instanceof IntInsnNode value && value.operand==6) {
            value.operand=7;break;
        }
        int unchanged=changedSink.instructions.size();
        if(AdvanceCompatibility.installDispatch(changedLoop) || dispatchCalls(changedSink)!=0
                || changedSink.instructions.size()!=unchanged)
            throw new AssertionError("Unexpected writer loop must remain unmodified");
        ClassNode configured=mergedWriter();AdvanceCompatibility.configure(configured);
        if(dispatchCalls(sink(configured))!=1)throw new AssertionError("Supported load-time configuration missed dispatch");
        ClassNode incompatible=mergedWriter();
        next(incompatible).instructions.insert(new MethodInsnNode(Opcodes.INVOKESTATIC,"other/Hook","next","()V",false));
        AdvanceCompatibility.configure(incompatible);
        MethodNode fallback=incompatible.methods.stream().filter(m->m.name.equals("psa$tryAdvanceEntityBase")).findFirst().orElseThrow();
        if(dispatchCalls(sink(incompatible))!=0 || fallback.instructions.getFirst().getOpcode()!=Opcodes.ICONST_0)
            throw new AssertionError("Foreign hook must retain the original writer and disable bulk advance");
        System.out.println("PASS real Embeddium method and unsupported-hook/body/missing/ambiguous rejection");
    }
}
