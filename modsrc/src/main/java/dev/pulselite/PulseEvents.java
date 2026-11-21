package dev.pulselite;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** FunTime-ивенты: ловит сообщения чата с координатами и показывает метку/стрелку/дистанцию. */
public final class PulseEvents {
    private PulseEvents() {}

    public static final class Marker {
        public String name; public double x, y, z; public boolean hasY; public long until;
    }
    public static final List<Marker> LIST = new ArrayList<>();
    private static final Pattern LABELED = Pattern.compile("(?i)x\\s*[:=]?\\s*(-?\\d+)[^\\d-]{0,14}?(?:y\\s*[:=]?\\s*(-?\\d+)[^\\d-]{0,14}?)?z\\s*[:=]?\\s*(-?\\d+)");
    private static final Pattern TRIPLE = Pattern.compile("(-?\\d{1,6})\\s*[,;\\s]\\s*(-?\\d{1,3})\\s*[,;\\s]\\s*(-?\\d{1,6})");
    private static final Pattern PAIR = Pattern.compile("(-?\\d{2,6})\\s*[,;\\s]\\s*(-?\\d{2,6})");

    public static void onMessage(String raw) {
        PulseConfig c = PulseConfig.get();
        if (!c.eventTracker || raw == null) return;
        String text = raw.replaceAll("§.", "");
        String low = text.toLowerCase();
        String key = null;
        for (String k : c.eventKeywords) if (low.contains(k.toLowerCase())) { key = k; break; }
        if (key == null) return;
        double x, y = 0, z; boolean hasY = false;
        Matcher m = LABELED.matcher(text);
        if (m.find()) {
            x = Double.parseDouble(m.group(1)); z = Double.parseDouble(m.group(3));
            if (m.group(2) != null) { y = Double.parseDouble(m.group(2)); hasY = true; }
        } else if ((m = TRIPLE.matcher(text)).find()) {
            x = Double.parseDouble(m.group(1)); y = Double.parseDouble(m.group(2)); z = Double.parseDouble(m.group(3)); hasY = true;
        } else if (low.contains("координат") && (m = PAIR.matcher(text)).find()) {
            x = Double.parseDouble(m.group(1)); z = Double.parseDouble(m.group(2));
        } else return;
        String name = text.substring(0, Math.min(text.length(), m.start())).replaceAll("[\\[\\]:>\\-–—•]+", " ").trim();
        if (name.length() > 26) name = name.substring(name.length() - 26).trim();
        if (name.isEmpty()) name = key.substring(0, 1).toUpperCase() + key.substring(1);
        add(name, x, y, z, hasY, true);
    }

    public static void add(String name, double x, double y, double z, boolean hasY, boolean announce) {
        PulseConfig c = PulseConfig.get();
        for (Marker o : LIST) if (Math.abs(o.x - x) < 8 && Math.abs(o.z - z) < 8) { o.until = System.currentTimeMillis() + c.eventTimeout * 1000L; return; }
        Marker k = new Marker();
        k.name = name; k.x = x; k.y = y; k.z = z; k.hasY = hasY;
        k.until = System.currentTimeMillis() + c.eventTimeout * 1000L;
        LIST.add(k);
        Minecraft mc = Minecraft.getInstance();
        if (announce) {
            if (c.eventSound) PulseSounds.play("event_alert", 1f, 1f);
            if (mc.gui != null) mc.gui.setOverlayMessage(Component.literal("⚑ " + name + "  X " + (int) x + (hasY ? " Y " + (int) y : "") + " Z " + (int) z), false);
        }
    }

    public static void test() {
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null) return;
        double a = Math.toRadians(mc.player.getYRot());
        add("Тестовый ивент", mc.player.getX() - Math.sin(a) * 120, mc.player.getY() + 10, mc.player.getZ() + Math.cos(a) * 120, true, true);
    }

    private static final String[] ARROWS = {"↑", "↗", "→", "↘", "↓", "↙", "←", "↖"};

    private static String arrowFor(Minecraft mc, Marker k) {
        double dx = k.x - mc.player.getX(), dz = k.z - mc.player.getZ();
        double tgt = Math.toDegrees(Math.atan2(-dx, dz));
        double rel = ((tgt - mc.player.getYRot()) % 360 + 540) % 360 - 180;
        return ARROWS[Math.floorMod((int) Math.round(rel / 45.0), 8)];
    }

    public static void render(GuiGraphics g, Minecraft mc) {
        PulseConfig c = PulseConfig.get();
        if (!c.eventTracker || mc.player == null) return;
        long now = System.currentTimeMillis();
        LIST.removeIf(k -> k.until < now || Math.hypot(k.x - mc.player.getX(), k.z - mc.player.getZ()) < 4);
        if (LIST.isEmpty()) return;
        int sw = mc.getWindow().getGuiScaledWidth(), sh = mc.getWindow().getGuiScaledHeight();
        double px = mc.player.getX(), py = mc.player.getEyeY(), pz = mc.player.getZ();
        double yaw = Math.toRadians(mc.player.getYRot()), pit = Math.toRadians(mc.player.getXRot());
        double fx = -Math.sin(yaw) * Math.cos(pit), fy = -Math.sin(pit), fz = Math.cos(yaw) * Math.cos(pit);
        double rx = -Math.cos(yaw), rz = -Math.sin(yaw);
        double ux = -rz * fy, uy = rz * fx - rx * fz, uz = rx * fy;
        double tf = Math.tan(Math.toRadians(mc.options.fov().get()) / 2.0), asp = (double) sw / sh;
        int accent = PulseTheme.accent(c.menuPreset) | 0xFF000000;
        int accRgb = accent & 0xFFFFFF;

        List<Marker> sorted = new ArrayList<>(LIST);
        sorted.sort((a, b) -> Double.compare(Math.hypot(a.x - px, a.z - pz), Math.hypot(b.x - px, b.z - pz)));

        // ---- метки в мире
        if (c.eventMarker) {
            int shown = 0;
            for (Marker k : sorted) {
                if (shown++ >= 4) break;
                double dx = k.x - px, dy = (k.hasY ? k.y : py) - py, dz = k.z - pz;
                double dist = Math.sqrt(dx * dx + dz * dz);
                double cz = dx * fx + dy * fy + dz * fz, cx = dx * rx + dz * rz, cy = dx * ux + dy * uy + dz * uz;
                int mx, my;
                if (cz > 0.1) {
                    mx = (int) (sw / 2.0 + (cx / cz) / (tf * asp) * sw / 2.0);
                    my = (int) (sh / 2.0 - (cy / cz) / tf * sh / 2.0);
                } else { mx = cx >= 0 ? sw : 0; my = sh / 2; }
                boolean off = mx < 14 || mx > sw - 14 || my < 24 || my > sh - 30;
                String glyph = "◆";
                if (off) {
                    mx = Math.max(16, Math.min(sw - 16, mx));
                    my = Math.max(26, Math.min(sh - 34, my));
                    glyph = arrowFor(mc, k);
                }
                String dist_s = (int) dist + " м";
                String label = c.eventMarkerStyle == 0 ? k.name + " · " + dist_s : dist_s;
                int w = Gfx.width(label) + 12;
                int lx = Math.max(2, Math.min(sw - w - 2, mx - w / 2));
                float pulse = 0.5f + 0.5f * (float) Math.sin(now / 350.0);
                Gfx.rr(g, lx, my - 20, w, 14, 0xB0050818);
                Gfx.border(g, lx, my - 20, w, 14, Gfx.argb(0x90 + (int) (pulse * 0x6F), accRgb));
                Gfx.text(g, label, lx + 6, my - 16, 0xFFFFFFFF);
                int gs = Gfx.width(glyph);
                Gfx.rr(g, mx - 7, my - 5, 14, 12, Gfx.argb(0xCC, accRgb));
                Gfx.text(g, glyph, mx - gs / 2, my - 3, 0xFFFFFFFF);
            }
        }

        // ---- список-панель
        if (!c.eventList) return;
        int max = Math.max(1, Math.min(6, c.eventMax));
        boolean card = c.eventStyle == 0;
        int rowH = card ? (c.eventCoords ? 26 : 18) : 12, pw = card ? 150 : 128, gap = card ? 3 : 1;
        int n = Math.min(max, sorted.size());
        boolean right = c.eventCorner == 1 || c.eventCorner == 3, bottom = c.eventCorner >= 2;
        int x = right ? sw - pw - 6 : 6;
        int total = n * (rowH + gap);
        int y = bottom ? sh - total - 40 : 40;
        for (int i = 0; i < n; i++) {
            Marker k = sorted.get(i);
            double dist = Math.hypot(k.x - px, k.z - pz);
            int left = (int) Math.max(0, (k.until - now) / 1000);
            String arrow = arrowFor(mc, k);
            String time = (left / 60) + ":" + (left % 60 < 10 ? "0" : "") + (left % 60);
            if (card) {
                Gfx.rr(g, x, y, pw, rowH, 0xC0050818);
                Gfx.border(g, x, y, pw, rowH, Gfx.argb(0x99, accRgb));
                g.fill(x + 1, y + 3, x + 3, y + rowH - 3, accent);
                Gfx.text(g, k.name, x + 8, y + 3, 0xFFFFFFFF);
                String right_s = (int) dist + " м " + arrow;
                Gfx.text(g, right_s, x + pw - Gfx.width(right_s) - 5, y + 3, accent);
                if (c.eventCoords) {
                    Gfx.text(g, "X " + (int) k.x + (k.hasY ? "  Y " + (int) k.y : "") + "  Z " + (int) k.z, x + 8, y + 14, 0xFF9AA6E8);
                    Gfx.text(g, time, x + pw - Gfx.width(time) - 5, y + 14, 0xFF7C86C8);
                }
            } else {
                String t = "⚑ " + k.name + " " + (int) dist + "м " + arrow;
                Gfx.text(g, t, right ? x + pw - Gfx.width(t) : x, y + 2, accent);
            }
            y += rowH + gap;
        }
    }
}
