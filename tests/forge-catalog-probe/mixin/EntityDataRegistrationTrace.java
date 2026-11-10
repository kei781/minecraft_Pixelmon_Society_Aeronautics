package dev.psa.catalogprobe.mixin;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializer;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Diagnostic only: no registry/constants/logging framework initialization here. */
@Mixin(value = SynchedEntityData.class, remap = false)
public abstract class EntityDataRegistrationTrace {
    @Inject(method = "m_135353_(Ljava/lang/Class;Lnet/minecraft/network/syncher/EntityDataSerializer;)Lnet/minecraft/network/syncher/EntityDataAccessor;",
            at = @At("RETURN"), require = 1)
    private static <T> void psa$traceRegistration(Class<? extends Entity> owner, EntityDataSerializer<T> serializer,
            CallbackInfoReturnable<EntityDataAccessor<T>> result) {
        StringBuilder callers = new StringBuilder();
        int retained = 0;
        for (StackTraceElement frame : Thread.currentThread().getStackTrace()) {
            if (frame.getClassName().equals("java.lang.Thread") || frame.getClassName().equals(SynchedEntityData.class.getName())) continue;
            if (retained++ == 4) break;
            if (callers.length() > 0) callers.append(" <- ");
            callers.append(frame.getClassName()).append('#').append(frame.getMethodName());
        }
        String line = "PSA_ENTITY_DATA owner=" + owner.getName() + " id=" + result.getReturnValue().getId()
                + " serializer_class=" + serializer.getClass().getName() + " callers=" + callers;
        System.out.println(line);
        // Prism captures raw stdout separately from latest.log. Use only JDK APIs here.
        synchronized (SynchedEntityData.class) {
            try {
                Path directory = Path.of("psa-validation");
                Files.createDirectories(directory);
                Files.writeString(directory.resolve("registration-trace.txt"), line + "\n",
                        StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } catch (IOException failure) {
                System.err.println("PSA_ENTITY_DATA_TRACE_FAILED " + failure);
            }
        }
    }
}
