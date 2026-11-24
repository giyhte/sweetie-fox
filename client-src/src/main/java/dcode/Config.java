package dcode;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import dcode.module.Module;
import dcode.module.ModuleManager;
import dcode.setting.Setting;
import net.fabricmc.loader.api.FabricLoader;

import java.nio.file.Files;
import java.nio.file.Path;

public class Config {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private static Path file() { return FabricLoader.getInstance().getConfigDir().resolve("dcode.json"); }

    public static void save() {
        try {
            JsonObject root = new JsonObject();
            for (Module m : ModuleManager.all()) {
                JsonObject o = new JsonObject();
                o.addProperty("enabled", m.isEnabled());
                JsonObject s = new JsonObject();
                for (Setting st : m.getSettings()) st.write(s);
                o.add("settings", s);
                root.add(m.getName(), o);
            }
            Files.writeString(file(), GSON.toJson(root));
        } catch (Exception ignored) {}
    }

    public static void load() {
        try {
            if (!Files.exists(file())) return;
            JsonObject root = JsonParser.parseString(Files.readString(file())).getAsJsonObject();
            for (Module m : ModuleManager.all()) {
                if (!root.has(m.getName())) continue;
                JsonObject o = root.getAsJsonObject(m.getName());
                if (o.has("settings")) for (Setting st : m.getSettings()) st.read(o.getAsJsonObject("settings"));
                if (o.has("enabled")) m.setEnabled(o.get("enabled").getAsBoolean());
            }
        } catch (Exception ignored) {}
    }
}
