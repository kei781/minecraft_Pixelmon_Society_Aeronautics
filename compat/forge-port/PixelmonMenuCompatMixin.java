package dev.psa.compat;

import net.minecraft.client.gui.components.Button;
import net.minecraft.network.chat.contents.TranslatableContents;
import net.minecraftforge.client.event.ScreenEvent;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Keep custom/demo title screens when Pixelmon's cosmetic menu assumptions fail. */
@Pseudo
@Mixin(targets = "com.pixelmonmod.pixelmon.client.gui.override.main.MainMenuModifier", remap = false)
public abstract class PixelmonMenuCompatMixin {
    @Inject(method = "onPreRender", at = @At("HEAD"), cancellable = true, require = 1)
    private void psa$preserveCustomMenu(ScreenEvent.Init.Post event, CallbackInfo ci) {
        for (String key : new String[] {"menu.singleplayer", "menu.multiplayer", "menu.online"}) {
            boolean found = event.getListenersList().stream().anyMatch(listener ->
                    listener instanceof Button button
                    && button.getMessage().getContents() instanceof TranslatableContents text
                    && key.equalsIgnoreCase(text.getKey()));
            if (!found) {
                ci.cancel();
                return;
            }
        }
    }
}
