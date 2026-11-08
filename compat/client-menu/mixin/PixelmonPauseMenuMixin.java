package dev.psa.clientmenu.mixin;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import net.minecraft.client.gui.components.Button;
import net.minecraft.network.chat.contents.TranslatableContents;
import net.minecraftforge.client.event.ScreenEvent;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.loading.FMLPaths;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Keep Society's Wiki/Credits row instead of Pixelmon's duplicate link row. */
@Pseudo
@Mixin(targets = "com.pixelmonmod.pixelmon.client.gui.override.escape.cosmetic.EscapeMenuCosmeticModifier", remap = false)
public abstract class PixelmonPauseMenuMixin {
    @Unique private static final String PSA_LAYOUT_SHA256 =
            "9ff6fe3965bc9b74aa1034f0588aeb337ae159529c118444d5d9cb5c30a6b30e";

    @Inject(method = "onPreRender", at = @At("RETURN"), require = 1)
    private void psa$preserveSocietyLinks(ScreenEvent.Init.Post event, CallbackInfo ci) {
        if (!ModList.get().isLoaded("society") || !ModList.get().isLoaded("fancymenu")) return;
        Path layout = FMLPaths.CONFIGDIR.get().resolve("fancymenu/customization/pause_screen_layout.txt");
        try {
            if (!Files.isRegularFile(layout) || Files.size(layout) > 65536) return;
            String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(Files.readAllBytes(layout)));
            if (!PSA_LAYOUT_SHA256.equals(hash)) return;
        } catch (Exception unavailable) {
            return;
        }
        for (var listener : event.getListenersList()) {
            if (listener instanceof Button button
                    && button.getMessage().getContents() instanceof TranslatableContents text
                    && ("menu.sendFeedback".equals(text.getKey()) || "menu.reportBugs".equals(text.getKey()))) {
                button.visible = false;
                button.active = false;
            }
        }
    }
}
