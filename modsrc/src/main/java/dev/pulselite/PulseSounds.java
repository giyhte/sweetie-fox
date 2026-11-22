package dev.pulselite;

import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.resources.Identifier;
import net.minecraft.sounds.SoundEvent;

import java.util.HashMap;
import java.util.Map;

/** Звуки мода (assets/pulselite/sounds). LIB — общий список, из него выбирается звук для каждого события. */
public final class PulseSounds {
    private PulseSounds() {}

    /** Порядок первых пяти НЕ менять: старые конфиги хранят индекс. */
    public static final String[] LIB_IDS = {"hit_pon", "hit_kira", "hit_kyun", "hit_nya", "hit_pico",
            "hit_crit", "kill", "hurt", "event_alert", "ui_click", "toggle_on", "title_start"};
    public static final String[] LIB_NAMES = {"Пон", "Кира", "Кюн", "Ня", "Пико",
            "Крит", "Убийство", "Урон", "Тревога", "Клик", "Щелчок", "Старт"};
    public static final String[] PITCH_NAMES = {"Очень низкий", "Низкий", "Обычный", "Высокий", "Очень высокий"};
    private static final float[] PITCH = {0.7f, 0.85f, 1.0f, 1.2f, 1.45f};

    private static final Map<String, SoundEvent> CACHE = new HashMap<>();
    private static long lastUi;

    public static SoundEvent ev(String id) {
        return CACHE.computeIfAbsent(id, k -> SoundEvent.createVariableRangeEvent(Identifier.fromNamespaceAndPath("pulselite", k)));
    }

    public static float pitch(int idx) { return PITCH[Math.floorMod(idx, PITCH.length)]; }

    public static void play(String id, float pitch, float vol) {
        try {
            Minecraft mc = Minecraft.getInstance();
            if (mc != null) mc.getSoundManager().play(SimpleSoundInstance.forUI(ev(id), pitch, Math.max(0f, vol)));
        } catch (Throwable t) { /* звук не критичен */ }
    }

    /** Проиграть звук из библиотеки с настройками (тип / громкость % / тон-индекс). */
    public static void playLib(int type, int volumePct, int pitchIdx) {
        play(LIB_IDS[Math.floorMod(type, LIB_IDS.length)], pitch(pitchIdx), volumePct / 100f);
    }

    public static void ui(String id) {
        PulseConfig c = PulseConfig.get();
        if (!c.uiSounds) return;
        long now = System.currentTimeMillis();
        if (id.equals("ui_hover")) {            // не заваливаем звуковой движок наведением
            if (now - lastUi < 90) return;
        }
        lastUi = now;
        play(id, 1f, c.uiVolume / 100f);
    }
}
