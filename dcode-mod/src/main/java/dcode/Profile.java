package dcode;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.MinecraftClient;

import java.nio.file.Files;
import java.nio.file.Path;

/** Профиль из лаунчера (dcode_profile.json): ник, аккаунт, срок лицензии. */
public class Profile {
    public static String account = "";
    public static long expiresAt = -1;   // 0 = навсегда, -1 = нет данных/истекла, иначе unix-секунды
    public static boolean loaded;

    public static void load() {
        try {
            Path f = FabricLoader.getInstance().getGameDir().resolve("dcode_profile.json");
            if (!Files.exists(f)) return;
            JsonObject o = JsonParser.parseString(Files.readString(f)).getAsJsonObject();
            account = o.has("account") ? o.get("account").getAsString() : "";
            expiresAt = o.has("expires_at") ? o.get("expires_at").getAsLong() : -1;
            loaded = true;
        } catch (Exception ignored) {}
    }

    public static String nick() {
        return MinecraftClient.getInstance().getSession().getUsername();
    }

    private static long leftSeconds() { return expiresAt - System.currentTimeMillis() / 1000; }

    public static boolean licenseOk() {
        return loaded && (expiresAt == 0 || (expiresAt > 0 && leftSeconds() > 0));
    }

    public static String licenseText() {
        if (!loaded) return "нет данных";
        if (expiresAt == 0) return "навсегда";
        long s = leftSeconds();
        if (expiresAt < 0 || s <= 0) return "истекла";
        return (s / 86400) + " д. " + ((s % 86400) / 3600) + " ч.";
    }
}
