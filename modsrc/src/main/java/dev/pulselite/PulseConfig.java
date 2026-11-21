package dev.pulselite;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;

import java.nio.file.Files;
import java.nio.file.Path;

public final class PulseConfig {
    public boolean hudFps = true;
    public boolean hudCoords = false;
    public boolean hudRam = false;
    public boolean hudTime = false;
    public boolean hudBackground = true;
    public int hudCorner = 0;
    public boolean zoom = true;
    public boolean customTitle = true;
    public boolean menuAnimated = true;
    public int menuPreset = 0;
    public int zoomFov = 30;
    public boolean boostOn = false;
    public int lastSky = 1;
    public boolean eventList = true;
    public int eventCorner = 1;
    public int eventStyle = 0;
    public int eventMax = 3;
    public boolean eventCoords = true;
    public int eventMarkerStyle = 0;
    public boolean uiSounds = true;
    public int uiVolume = 60;
    public boolean hitSound = true;
    public int hitType = 0;
    public int hitVolume = 80;
    public boolean critSound = true;
    public boolean killSound = true;
    public boolean hurtSound = false;
    public boolean autoSprint = true;
    public int skyPreset = 0;
    public int skyIntensity = 60;
    public boolean eventTracker = true;
    public boolean eventMarker = true;
    public boolean eventSound = true;
    public int eventTimeout = 600;
    public boolean petals = true;
    public String[] eventKeywords = {"ивент","event","аирдроп","airdrop","метеорит","смерч","шторм","босс","сундук","маяк","вулкан","дроп"};

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
