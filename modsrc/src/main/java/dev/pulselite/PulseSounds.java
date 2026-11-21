package dev.pulselite;

import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.resources.Identifier;
import net.minecraft.sounds.SoundEvent;

import java.util.HashMap;
import java.util.Map;

/** Анимешные звуки (assets/pulselite/sounds). */
public final class PulseSounds {
    private PulseSounds() {}
    public static final String[] HIT_IDS = {"hit_pon", "hit_kira", "hit_kyun", "hit_nya", "hit_pico"};
    public static final String[] HIT_NAMES = {"Пон", "Кира", "Кюн", "Ня", "Пико"};
    private static final Map<String, SoundEvent> CACHE = new HashMap<>();

    public static SoundEvent ev(String id) {
        return CACHE.computeIfAbsent(id, k -> SoundEvent.createVariableRangeEvent(Identifier.fromNamespaceAndPath("pulselite", k)));
    }

    public static void play(String id, float pitch, float vol) {
        try {
            Minecraft mc = Minecraft.getInstance();
            if (mc != null) mc.getSoundManager().play(SimpleSoundInstance.forUI(ev(id), pitch, vol));
        } catch (Throwable t) { /* звук не критичен */ }
    }

    public static void ui(String id) {
        PulseConfig c = PulseConfig.get();
        if (c.uiSounds) play(id, 1f, c.uiVolume / 100f);
    }
}
