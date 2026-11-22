package dev.pulselite;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;

import java.nio.file.Files;
import java.nio.file.Path;

public final class PulseConfig {
    // ---- Основное: HUD
    public boolean hudFps = true;
    public boolean hudPing = true;
    public boolean hudCoords = false;
    public boolean hudRam = false;
    public boolean hudTime = false;
    public boolean hudSpeed = false;
    public boolean hudDir = false;
    public boolean hudBackground = true;
    public int hudCorner = 0;
    public int hudScale = 100;
    // ---- Основное: оформление
    public boolean customTitle = true;
    public boolean menuAnimated = true;
    public boolean petals = true;
    public int menuPreset = 0;
    public boolean uiSounds = true;
    public int uiVolume = 60;
    // ---- Визуалы: звуки (type = индекс в PulseSounds.LIB, pitch = индекс 0..4)
    public boolean hitSound = true;
    public int hitType = 0, hitVolume = 80, hitPitch = 2;
    public boolean critSound = true;
    public int critType = 5, critVolume = 90, critPitch = 2;
    public boolean killSound = true;
    public int killType = 6, killVolume = 100, killPitch = 2;
    // ---- Визуалы: ивенты FunTime
    public boolean eventTracker = true;
    public boolean eventList = true;
    public int eventCorner = 1;
    public int eventStyle = 0;
    public int eventMax = 3;
    public boolean eventCoords = true;
    public boolean eventMarker = true;
    public int eventMarkerStyle = 0;
    public boolean eventSound = true;
    public int eventSoundType = 8, eventVolume = 100, eventPitch = 2;
    public int eventTimeout = 600;
    /** id типов ивентов, которые ВЫКЛЮЧЕНЫ (нет в списке = показывается). */
    public java.util.List<String> eventOff = new java.util.ArrayList<>();
    /** id типов ивентов, у которых выключен звук. */
    public java.util.List<String> eventMute = new java.util.ArrayList<>();
    /** свои ключевые слова (добавляются к типу «Другое»). */
    public String[] eventKeywords = {};

    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static PulseConfig inst = new PulseConfig();

    public static PulseConfig get() { return inst; }

    private static Path path() { return FabricLoader.getInstance().getConfigDir().resolve("pulselite.json"); }

    public static void load() {
        try {
            Path p = path();
            if (Files.exists(p)) {
                PulseConfig c = GSON.fromJson(Files.readString(p), PulseConfig.class);
                if (c != null) inst = c;
            }
        } catch (Exception e) {
            System.err.println("[PulseLite] config load failed: " + e);
        }
        if (inst.menuPreset < 0 || inst.menuPreset >= PulseTheme.NAMES.length) inst.menuPreset = 0;
        if (inst.eventOff == null) inst.eventOff = new java.util.ArrayList<>();
        if (inst.eventMute == null) inst.eventMute = new java.util.ArrayList<>();
        if (inst.eventKeywords == null) inst.eventKeywords = new String[0];
    }

    public static void save() {
        try {
            Files.writeString(path(), GSON.toJson(inst));
        } catch (Exception e) {
            System.err.println("[PulseLite] config save failed: " + e);
        }
    }

    public static void reset() { inst = new PulseConfig(); save(); }
}
