package dev.psa.menuprobe;

import com.mojang.logging.LogUtils;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.network.chat.contents.TranslatableContents;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.client.gui.LoadingErrorScreen;
import org.slf4j.Logger;
import java.util.ArrayList;
import java.util.List;

/** Isolated client fixture; not evidence of authentication or gameplay. */
@Mod("psamenuprobe")
public final class MenuProbe {
    @Mod.EventBusSubscriber(modid = "psamenuprobe", value = Dist.CLIENT)
    public static final class Client {
        private static final Logger LOG = LogUtils.getLogger();
        private static int ticks;
        private static boolean opened;
        private static boolean recorded;
        private static int scale = 2;

        @SubscribeEvent
        public static void tick(TickEvent.ClientTickEvent event) {
            if (event.phase != TickEvent.Phase.END || recorded) return;
            Minecraft client = Minecraft.getInstance();
            if (!opened && client.screen != null && client.player == null && client.getOverlay() == null) {
                if (++ticks < 40) return;
                if (client.screen instanceof LoadingErrorScreen) {
                    try {
                        var field = LoadingErrorScreen.class.getDeclaredField("modLoadErrors");
                        field.setAccessible(true);
                        List<?> errors = (List<?>) field.get(client.screen);
                        LOG.info("PSA_MENU_PROBE loading_errors={}", errors.size());
                        if (!errors.isEmpty()) throw new IllegalStateException("Fatal mod loading errors");
                    } catch (Exception failure) {
                        recorded = true;
                        LOG.error("PSA_MENU_PROBE FAILED loading guard", failure);
                        return;
                    }
                }
                LOG.info("PSA_MENU_PROBE fixture_start previous_screen={}", client.screen.getClass().getName());
                opened = true;
                ticks = 0;
                client.options.guiScale().set(scale);
                client.resizeDisplay();
                client.setScreen(new PauseScreen(true));
            } else if (opened && client.screen instanceof PauseScreen && ++ticks == 100) {
                int visible = 0;
                var buttons = new ArrayList<AbstractWidget>();
                for (var child : client.screen.children()) {
                    if (!(child instanceof AbstractWidget widget)) continue;
                    String key = widget.getMessage().getContents() instanceof TranslatableContents text
                            ? text.getKey() : "literal";
                    LOG.info("PSA_MENU_PROBE scale={} widget={} key={} label={} x={} y={} w={} h={} visible={} active={}",
                            scale, child.getClass().getName(), key, widget.getMessage().getString(),
                            widget.getX(), widget.getY(), widget.getWidth(), widget.getHeight(),
                            widget.visible, widget.active);
                    if (widget.visible) visible++;
                    if (widget instanceof Button && widget.visible && widget.active) buttons.add(widget);
                }
                int overlaps = 0;
                for (int a = 0; a < buttons.size(); a++) {
                    for (int b = a + 1; b < buttons.size(); b++) {
                        var one = buttons.get(a);
                        var two = buttons.get(b);
                        if (one.getX() < two.getX() + two.getWidth() && two.getX() < one.getX() + one.getWidth()
                                && one.getY() < two.getY() + two.getHeight() && two.getY() < one.getY() + one.getHeight()) {
                            overlaps++;
                            LOG.info("PSA_MENU_PROBE OVERLAP scale={} first={} second={}",
                                    scale, one.getMessage().getString(), two.getMessage().getString());
                        }
                    }
                }
                LOG.info("PSA_MENU_PROBE SUMMARY scale={} width={} height={} visible_widgets={} active_button_overlaps={}",
                        scale, client.screen.width, client.screen.height, visible, overlaps);
                if (++scale <= 4) {
                    ticks = 0;
                    client.options.guiScale().set(scale);
                    client.resizeDisplay();
                } else {
                    recorded = true;
                    LOG.info("PSA_MENU_PROBE COMPLETE cases=3");
                }
            }
        }
    }
}
