package dev.psa.menuprobe;

import com.mojang.logging.LogUtils;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.contents.TranslatableContents;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.client.gui.LoadingErrorScreen;
import net.minecraftforge.fml.loading.FMLPaths;
import org.slf4j.Logger;
import java.util.ArrayList;
import java.util.List;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HexFormat;
import java.security.MessageDigest;

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
        private static int scenario;
        private static final String[] SCENARIOS = {"default", "changed-layout", "disabled-layout", "disabled-screen"};
        private static byte[] originalLayout;
        private static byte[] originalScreens;
        private static final Path LAYOUT = FMLPaths.CONFIGDIR.get().resolve("fancymenu/customization/pause_screen_layout.txt");
        private static final Path SCREENS = FMLPaths.CONFIGDIR.get().resolve("fancymenu/customizablemenus.txt");

        private static void restoreFiles() throws Exception {
            if (originalLayout != null) Files.write(LAYOUT, originalLayout);
            if (originalScreens != null) Files.write(SCREENS, originalScreens);
        }

        private static void openScenario(Minecraft client) throws Exception {
            byte[] layout = originalLayout;
            byte[] screens = originalScreens;
            if (scenario == 1) {
                layout = Arrays.copyOf(originalLayout, originalLayout.length + 1);
                layout[layout.length - 1] = '\n';
            } else if (scenario == 2) {
                String original = new String(originalLayout, StandardCharsets.UTF_8);
                String disabled = original.replace("  is_enabled = true", "  is_enabled = false");
                if (original.equals(disabled)) throw new IllegalStateException("Layout enabled marker absent");
                layout = disabled.getBytes(StandardCharsets.UTF_8);
            } else if (scenario == 3) {
                String original = new String(originalScreens, StandardCharsets.UTF_8);
                String disabled = original.replaceAll("(?s)net\\.minecraft\\.client\\.gui\\.screens\\.PauseScreen\\s*\\{[^}]*\\}", "");
                if (original.equals(disabled)) throw new IllegalStateException("Pause customization registry absent");
                screens = disabled.getBytes(StandardCharsets.UTF_8);
            }
            Files.write(LAYOUT, layout);
            Files.write(SCREENS, screens);
            Class<?> api = Class.forName("de.keksuccino.fancymenu.customization.ScreenCustomization");
            api.getMethod("readCustomizableScreensFromFile").invoke(null);
            api.getMethod("reloadFancyMenu").invoke(null);
            scale = 2;
            ticks = 0;
            client.options.guiScale().set(scale);
            client.resizeDisplay();
            client.setScreen(new PauseScreen(true));
            Object enabled = api.getMethod("isCustomizationEnabledForScreen", Screen.class).invoke(null, client.screen);
            LOG.info("PSA_MENU_PROBE SCENARIO name={} screen_customization_enabled={} layout_sha256={}",
                    SCENARIOS[scenario], enabled, HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                            .digest(Files.readAllBytes(LAYOUT))));
        }

        private static void fail(Exception failure) {
            recorded = true;
            LOG.error("PSA_MENU_PROBE FAILED", failure);
            try { restoreFiles(); }
            catch (Exception restoreFailure) { LOG.error("PSA_MENU_PROBE FAILED restore", restoreFailure); }
        }

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
                try {
                    originalLayout = Files.readAllBytes(LAYOUT);
                    originalScreens = Files.readAllBytes(SCREENS);
                    openScenario(client);
                } catch (Exception failure) { fail(failure); }
            } else if (opened && client.screen instanceof PauseScreen && ++ticks == 100) {
                int visible = 0;
                var buttons = new ArrayList<AbstractWidget>();
                for (var child : client.screen.children()) {
                    if (!(child instanceof AbstractWidget widget)) continue;
                    String key = widget.getMessage().getContents() instanceof TranslatableContents text
                            ? text.getKey() : "literal";
                    LOG.info("PSA_MENU_PROBE scenario={} scale={} widget={} key={} label={} x={} y={} w={} h={} visible={} active={}",
                            SCENARIOS[scenario], scale, child.getClass().getName(), key, widget.getMessage().getString(),
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
                            LOG.info("PSA_MENU_PROBE OVERLAP scenario={} scale={} first={} second={}",
                                    SCENARIOS[scenario], scale, one.getMessage().getString(), two.getMessage().getString());
                        }
                    }
                }
                LOG.info("PSA_MENU_PROBE SUMMARY scenario={} scale={} width={} height={} visible_widgets={} active_button_overlaps={}",
                        SCENARIOS[scenario], scale, client.screen.width, client.screen.height, visible, overlaps);
                if (++scale <= 4) {
                    ticks = 0;
                    client.options.guiScale().set(scale);
                    client.resizeDisplay();
                } else {
                    try {
                        if (++scenario < SCENARIOS.length) openScenario(client);
                        else {
                            recorded = true;
                            restoreFiles();
                            LOG.info("PSA_MENU_PROBE COMPLETE cases=12 configs_restored=true");
                        }
                    } catch (Exception failure) { fail(failure); }
                }
            }
        }
    }
}
