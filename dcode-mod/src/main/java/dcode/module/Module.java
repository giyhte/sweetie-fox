package dcode.module;

import dcode.setting.Setting;
import net.minecraft.client.MinecraftClient;

import java.util.ArrayList;
import java.util.List;

public abstract class Module {
    protected static final MinecraftClient mc = MinecraftClient.getInstance();
    private final String name;
    private final Category category;
    private final String description;
    private boolean enabled;
    private int key = -1;          // GLFW-код клавиши, -1 = не назначена
    public boolean keyDown;
    private final List<Setting> settings = new ArrayList<>();

    protected Module(String name, Category category, String description) {
        this.name = name;
        this.category = category;
        this.description = description;
    }

    protected <S extends Setting> S add(S s) { settings.add(s); return s; }

    public String getName() { return name; }
    public Category getCategory() { return category; }
    public String getDescription() { return description; }
    public int getKey() { return key; }
    public void setKey(int key) { this.key = key; }
    public boolean isEnabled() { return enabled; }
    public List<Setting> getSettings() { return settings; }

    public void toggle() { setEnabled(!enabled); }

    public void setEnabled(boolean value) {
        if (value == enabled) return;
        enabled = value;
        if (value) onEnable(); else onDisable();
    }

    protected void onEnable() {}
    protected void onDisable() {}
    public void onTick() {}
}
