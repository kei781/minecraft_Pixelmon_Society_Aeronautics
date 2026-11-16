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

    public static void disableUnsupported(ClassNode node) {
        if(supports(node))return;
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
