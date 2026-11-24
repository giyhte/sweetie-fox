package dcode.setting;

import com.google.gson.JsonObject;

public abstract class Setting {
    public final String name;
    protected Setting(String name) { this.name = name; }
    public abstract void write(JsonObject o);
    public abstract void read(JsonObject o);
}
