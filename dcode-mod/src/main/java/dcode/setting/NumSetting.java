package dcode.setting;

import com.google.gson.JsonObject;

public class NumSetting extends Setting {
    public final double min, max, step;
    private double value;
    public NumSetting(String name, double def, double min, double max, double step) {
        super(name); this.min = min; this.max = max; this.step = step; this.value = def;
    }
    public double get() { return value; }
    public int getInt() { return (int) Math.round(value); }
    public void set(double v) {
        v = Math.round(v / step) * step;
        value = Math.max(min, Math.min(max, v));
    }
    public String format() { return step >= 1 ? String.valueOf((int) Math.round(value)) : String.format("%.1f", value); }
    @Override public void write(JsonObject o) { o.addProperty(name, value); }
    @Override public void read(JsonObject o) { if (o.has(name)) set(o.get(name).getAsDouble()); }
}
