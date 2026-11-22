package dev.pulselite;

import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class PulseHud {
    private PulseHud() {}

    private static String ping(Minecraft mc) {
        try {
            var cn = mc.getConnection();
            if (cn == null) return "—";
            var pi = cn.getPlayerInfo(mc.player.getUUID());
            return pi == null ? "—" : pi.getLatency() + " мс";
        } catch (Throwable t) { return "—"; }
    }

    private static String dir(Minecraft mc) {
        String n = mc.player.getDirection().getName();
        switch (n) {
            case "north": return "Север";
            case "south": return "Юг";
            case "east": return "Восток";
            case "west": return "Запад";
            default: return n;
        }
    }

    public static void render(GuiGraphics g, DeltaTracker dt) {
        Minecraft mc = Minecraft.getInstance();
        PulseConfig c = PulseConfig.get();
        if (mc.player == null || mc.options.hideGui) return;
        if (!PulseLicense.pending() && !PulseLicense.valid()) return;
        try {
            PulseEvents.render(g, mc);
        } catch (Throwable t) { /* HUD не должен ронять игру */ }
        List<String> lines = new ArrayList<>();
        List<Integer> cols = new ArrayList<>();
        if (c.hudFps) {
            int f = mc.getFps();
            lines.add("FPS " + f);
            cols.add(f >= 60 ? 0xFF7CF29A : f >= 30 ? 0xFFFFD36B : 0xFFFF7A8A);
        }
        if (c.hudPing) { lines.add("Пинг " + ping(mc)); cols.add(0xFFFFFFFF); }
        if (c.hudCoords) {
            lines.add("XYZ " + mc.player.getBlockX() + " " + mc.player.getBlockY() + " " + mc.player.getBlockZ());
            cols.add(0xFFFFFFFF);
        }
        if (c.hudDir) { lines.add("Курс " + dir(mc)); cols.add(0xFFFFFFFF); }
        if (c.hudSpeed) {
            double sp = mc.player.getDeltaMovement().horizontalDistance() * 20.0;
            lines.add("Скорость " + String.format(Locale.ROOT, "%.1f", sp) + " б/с");
            cols.add(0xFFFFFFFF);
        }
        if (c.hudRam) {
            Runtime r = Runtime.getRuntime();
            lines.add("ОЗУ " + ((r.totalMemory() - r.freeMemory()) >> 20) + "/" + (r.maxMemory() >> 20) + " МБ");
            cols.add(0xFFFFFFFF);
        }
        if (c.hudTime) { lines.add(LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))); cols.add(0xFFFFFFFF); }
        if (lines.isEmpty()) return;

        float sc = Math.max(50, Math.min(200, c.hudScale)) / 100f;
        int w = 0;
        for (String s : lines) w = Math.max(w, Gfx.width(s));
        int h = lines.size() * 10;
        int sw = mc.getWindow().getGuiScaledWidth();
        int sh = mc.getWindow().getGuiScaledHeight();
        int bw = (int) ((w + 10) * sc), bh = (int) ((h + 4) * sc);
        int x = (c.hudCorner % 2 == 0) ? 4 : sw - bw - 4;
        int y = (c.hudCorner < 2) ? 4 : sh - bh - 4;
        int accent = PulseTheme.accent(c.menuPreset);
        g.pose().pushMatrix();
        g.pose().translate((float) x, (float) y);
        g.pose().scale(sc, sc);
        if (c.hudBackground) {
            Gfx.rr(g, 0, 0, w + 10, h + 4, 0x70000000);
            g.fill(0, 2, 1, h + 2, accent);
        }
        for (int i = 0; i < lines.size(); i++) Gfx.text(g, lines.get(i), 6, 2 + i * 10, cols.get(i));
        g.pose().popMatrix();
    }
}
