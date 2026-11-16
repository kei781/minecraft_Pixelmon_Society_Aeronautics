package dev.psa.pixelmonrender;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.*;

/** Checks the observed nextElement body before bypassing any of its calls. */
public final class AdvanceCompatibility {
    // Canonical opcode/operand digest of pinned Embeddium 0.3.31's nextElement.
    // Labels/frames/line numbers are ignored and the target's owner is normalized.
    private static final String EXPECTED="16a50068319d2d689abbd758c25abebe62aeedf8a6e9bf2e9f50adc72feee9ef";
    private AdvanceCompatibility() { }

    public static boolean supports(ClassNode node) {
        MethodNode method=null;
        for(MethodNode candidate:node.methods) if(candidate.name.equals("m_5751_") && candidate.desc.equals("()V")) {
            if(method!=null)return false;
            method=candidate;
        }
        if(method==null || method.access!=Opcodes.ACC_PUBLIC || !method.tryCatchBlocks.isEmpty())return false;
        IdentityHashMap<AbstractInsnNode,Integer> indices=new IdentityHashMap<>(); int index=0;
        for(AbstractInsnNode instruction:method.instructions)
            if(instruction.getOpcode()>=0)indices.put(instruction,index++);
        StringBuilder canonical=new StringBuilder();
        for(AbstractInsnNode instruction:method.instructions) {
            if(instruction.getOpcode()<0)continue;
            canonical.append(instruction.getOpcode()).append('|');
            if(instruction instanceof VarInsnNode n)canonical.append(n.var);
            else if(instruction instanceof FieldInsnNode n)
                canonical.append(owner(node,n.owner)).append(':').append(n.name).append(':').append(n.desc);
            else if(instruction instanceof MethodInsnNode n)
                canonical.append(owner(node,n.owner)).append(':').append(n.name).append(':').append(n.desc).append(':').append(n.itf);
            else if(instruction instanceof JumpInsnNode n) {
                AbstractInsnNode target=n.label;
                while(target!=null && target.getOpcode()<0)target=target.getNext();
                if(target==null || !indices.containsKey(target))return false;
                canonical.append(indices.get(target));
            } else if(!(instruction instanceof InsnNode))return false;
            canonical.append('\n');
        }
        try {
            return EXPECTED.equals(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(canonical.toString().getBytes(StandardCharsets.UTF_8))));
        } catch(NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }

    private static String owner(ClassNode node,String owner) { return owner.equals(node.name)?"SELF":owner; }

    /** Adds only a guarded jump around the authored six-step loop. No runtime OFF branch. */
    public static boolean installDispatch(ClassNode node) {
        MethodNode sink=null;boolean advance=false;
        for(MethodNode method:node.methods) {
            if(method.name.equals("psa$tryAdvanceEntityBase") && method.desc.equals("()Z"))advance=true;
            if(method.name.equals("psa$tryEntityVertex") && method.desc.equals("(FFFFFFFFFIIFFF)Z")) {
                if(sink!=null)return false;sink=method;
            }
        }
        if(sink==null || !advance)return false;
        MethodInsnNode call=null;
        for(AbstractInsnNode instruction:sink.instructions)if(instruction instanceof MethodInsnNode method) {
            if(method.name.equals("psa$tryAdvanceEntityBase"))return false;
            if(method.owner.equals(node.name) && method.name.equals("m_5751_") && method.desc.equals("()V")) {
                if(call!=null)return false;call=method;
            }
        }
        if(call==null || call.getOpcode()!=Opcodes.INVOKEVIRTUAL)return false;
        AbstractInsnNode receiver=previous(call);
        if(!(receiver instanceof VarInsnNode recv) || recv.getOpcode()!=Opcodes.ALOAD || recv.var!=0)return false;
        AbstractInsnNode guard=previous(receiver);
        if(!(guard instanceof JumpInsnNode condition) || condition.getOpcode()!=Opcodes.IF_ICMPGE)return false;
        AbstractInsnNode limit=previous(guard);
        if(!(limit instanceof IntInsnNode six) || six.getOpcode()!=Opcodes.BIPUSH || six.operand!=6)return false;
        AbstractInsnNode counter=previous(limit);
        if(!(counter instanceof VarInsnNode load) || load.getOpcode()!=Opcodes.ILOAD)return false;
        AbstractInsnNode store=previous(counter);
        if(!(store instanceof VarInsnNode init) || init.getOpcode()!=Opcodes.ISTORE || init.var!=load.var)return false;
        AbstractInsnNode zero=previous(store);
        if(zero==null || zero.getOpcode()!=Opcodes.ICONST_0)return false;
        AbstractInsnNode increment=next(call);
        if(!(increment instanceof IincInsnNode step) || step.var!=load.var || step.incr!=1)return false;
        AbstractInsnNode repeat=next(increment);
        if(!(repeat instanceof JumpInsnNode back) || back.getOpcode()!=Opcodes.GOTO || next(back.label)!=counter)return false;
        AbstractInsnNode endReceiver=next(condition.label),endCall=next(endReceiver);
        if(!(endReceiver instanceof VarInsnNode end) || end.getOpcode()!=Opcodes.ALOAD || end.var!=0
                || !(endCall instanceof MethodInsnNode finish) || finish.getOpcode()!=Opcodes.INVOKEVIRTUAL
                || !finish.owner.equals(node.name) || !finish.name.equals("m_5752_") || !finish.desc.equals("()V"))return false;
        InsnList dispatch=new InsnList();
        dispatch.add(new VarInsnNode(Opcodes.ALOAD,0));
        dispatch.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL,node.name,"psa$tryAdvanceEntityBase","()Z",false));
        dispatch.add(new JumpInsnNode(Opcodes.IFNE,condition.label));
        sink.instructions.insertBefore(zero,dispatch);
        return true;
    }

    private static AbstractInsnNode previous(AbstractInsnNode node) {
        if(node==null)return null;
        do {node=node.getPrevious();} while(node!=null && node.getOpcode()<0);
        return node;
    }
    private static AbstractInsnNode next(AbstractInsnNode node) {
        if(node==null)return null;
        do {node=node.getNext();} while(node!=null && node.getOpcode()<0);
        return node;
    }

    public static void configure(ClassNode node) {
        if(!supports(node) || !installDispatch(node))disable(node);
    }

    public static void disableUnsupported(ClassNode node) {
        if(supports(node))return;
        disable(node);
    }

    private static void disable(ClassNode node) {
        for(MethodNode method:node.methods) if(method.name.equals("psa$tryAdvanceEntityBase") && method.desc.equals("()Z")) {
            method.instructions.clear();
            method.instructions.add(new InsnNode(Opcodes.ICONST_0));
            method.instructions.add(new InsnNode(Opcodes.IRETURN));
            method.tryCatchBlocks.clear();
            if(method.localVariables!=null)method.localVariables.clear();
            method.maxStack=1; method.maxLocals=1;
            return;
        }
        throw new IllegalStateException("Authored advance method missing; refusing unchecked bypass");
    }
}
