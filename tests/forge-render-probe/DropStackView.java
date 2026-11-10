package dev.psa.renderprobe;

import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;

/** Explicit public carrier APIs in this pinned pack; no fabricated replacement entities. */
public final class DropStackView {
    private DropStackView() {}
    public static ItemStack stack(Entity entity) {
        if (entity instanceof ItemEntity item) return item.getItem();
        for (Class<?> type = entity.getClass(); type != null; type = type.getSuperclass()) {
            if (type.getName().equals("com.simibubi.create.content.logistics.box.PackageEntity")) {
                try { return (ItemStack) entity.getClass().getMethod("getBox").invoke(entity); }
                catch (ReflectiveOperationException failure) { throw new IllegalStateException("Pinned Create getBox API differs", failure); }
            }
        }
        return ItemStack.EMPTY;
    }
}
