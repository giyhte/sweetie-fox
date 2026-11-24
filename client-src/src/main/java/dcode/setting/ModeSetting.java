package dcode.setting;

import com.google.gson.JsonObject;

public class ModeSetting extends Setting {
    private final String[] modes;
    private int index;
    public ModeSetting(String name, int def, String... modes) { super(name); this.modes = modes; this.index = def; }
    public String get() { return modes[index]; }
    public int index() { return index; }
    public void cycle() { index = (index + 1) % modes.length; }
    @Override public void write(JsonObject o) { o.addProperty(name, index); }
    @Override public void read(JsonObject o) {
        if (o.has(name)) { int i = o.get(name).getAsInt(); if (i >= 0 && i < modes.length) index = i; }
    }
}
