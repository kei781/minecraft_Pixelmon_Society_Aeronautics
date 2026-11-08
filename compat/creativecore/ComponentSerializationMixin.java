/*
 * SPDX-License-Identifier: LGPL-3.0-only
 * Compatibility replacement for CreativeCore 2.13.51's mixin of the same name.
 * Original project: https://github.com/CreativeMD/CreativeCore
 * Modification: append CreativeCore's content type at the matcher input instead
 * of injecting into createCodec, which Pixelmon 9.4.1 overwrites.
 */
package team.creative.creativecore.mixin;

import java.util.Arrays;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import net.minecraft.network.chat.ComponentContents;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.util.StringRepresentable;
import team.creative.creativecore.common.util.text.content.ContentItemStack;

@Mixin(ComponentSerialization.class)
public class ComponentSerializationMixin {
    @SuppressWarnings("unchecked")
    @ModifyVariable(
        method = "createLegacyComponentMatcher([Lnet/minecraft/util/StringRepresentable;Ljava/util/function/Function;Ljava/util/function/Function;Ljava/lang/String;)Lcom/mojang/serialization/MapCodec;",
        at = @At("HEAD"), argsOnly = true, ordinal = 0, require = 1
    )
    private static <T extends StringRepresentable> T[] psa$addItemStackType(T[] types) {
        // The generic matcher is also used by NBT DataSource and other enums.
        // Extend only the component-content type table.
        if (!(types instanceof ComponentContents.Type<?>[])) {
            return types;
        }
        for (T type : types) {
            if (type == ContentItemStack.TYPE) {
                return types;
            }
        }
        T[] extended = Arrays.copyOf(types, types.length + 1);
        extended[types.length] = (T) ContentItemStack.TYPE;
        return extended;
    }
}
