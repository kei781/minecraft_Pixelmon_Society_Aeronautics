package dev.psa.menudata;

import java.util.Collections;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.world.inventory.ContainerData;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.inventory.SimpleContainerData;
import net.minecraftforge.registries.RegistryObject;

/** Keep one logical int intact while vanilla menu properties carry two short halves. */
public final class MenuIntData {
    // Values never retain their weak keys; each menu owns its logical data while open.
    private static final Map<ContainerData, Boolean> CLIENT_READY = Collections.synchronizedMap(new WeakHashMap<>());
    private MenuIntData() {}

    public static ContainerData wire(ContainerData logical) {
        if (logical.getCount() != 1) throw new IllegalArgumentException("Expected one int property");
        // The pinned client constructors allocate this exact vanilla data implementation.
        boolean client = logical instanceof SimpleContainerData;
        if (client) CLIENT_READY.put(logical, false);
        return new ContainerData() {
            private int low;
            private int high;
            private boolean receivedLow;
            private boolean receivedHigh;

            @Override public int get(int index) {
                return switch (index) {
                    case 0 -> logical.get(0) & 0xffff;
                    case 1 -> logical.get(0) >>> 16;
                    default -> throw new IndexOutOfBoundsException(index);
                };
            }

            @Override public void set(int index, int value) {
                switch (index) {
                    case 0 -> { low = value & 0xffff; receivedLow = true; }
                    case 1 -> { high = value & 0xffff; receivedHigh = true; }
                    default -> throw new IndexOutOfBoundsException(index);
                }
                // A menu may render between packets. Never expose an initial partial ID.
                if (receivedLow && receivedHigh) {
                    logical.set(0, low | (high << 16));
                    if (client) CLIENT_READY.put(logical, true);
                }
            }

            @Override public int getCount() { return 2; }
        };
    }

    public static boolean ready(ContainerData logical) {
        return !(logical instanceof SimpleContainerData) || Boolean.TRUE.equals(CLIENT_READY.get(logical));
    }

    public static MenuType<?> batteryMenuType() {
        try {
            RegistryObject<?> registered = (RegistryObject<?>) Class.forName("com.alc.moreminecarts.registry.MMContainers")
                    .getField("BATTERY_CART_CONTAINER").get(null);
            return (MenuType<?>) registered.get();
        } catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Pinned More Minecarts battery menu registry is unavailable", error);
        }
    }
}
