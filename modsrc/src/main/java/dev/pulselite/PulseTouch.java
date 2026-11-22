package dev.pulselite;

import net.fabricmc.fabric.api.client.screen.v1.ScreenEvents;
import net.fabricmc.fabric.api.client.screen.v1.Screens;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.network.chat.Component;

/**
 * Сенсорный способ открыть меню (для телефона, где нет Right Shift):
 * кнопка «Sweetie Menu» в углу экрана паузы (Esc). Работает и на ПК.
 */
public final class PulseTouch {
    private PulseTouch() {}

    public static void init() {
        ScreenEvents.AFTER_INIT.register((client, screen, w, h) -> {
            if (!(screen instanceof PauseScreen)) return;
            try {
                if (!PulseLicense.pending() && !PulseLicense.valid()) return;
                Button b = Button.builder(Component.literal("Sweetie Menu"), btn -> {
                    PulseSounds.ui("ui_open");
                    Minecraft.getInstance().setScreen(new PulseMenuScreen(screen));
                }).bounds(w - 112, 8, 104, 22).build();
                Screens.getButtons(screen).add(b);
            } catch (Throwable t) {
                System.err.println("[PulseLite] touch button: " + t);
            }
        });
    }
}
