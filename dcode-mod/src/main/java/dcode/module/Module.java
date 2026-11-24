package dcode.module;

import dcode.setting.Setting;
import net.minecraft.client.MinecraftClient;

import java.util.ArrayList;
import java.util.List;

public abstract class Module {
    protected static final MinecraftClient mc = MinecraftClient.getInstance();
    private final String name;
    private boolean enabled;
    private final List<Setting> settings = new ArrayList<>();

    protected Module(String name) { this.name = name; }

    protected <S extends Setting> S add(S s) { settings.add(s); return s; }

    public String getName() { return name; }
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
