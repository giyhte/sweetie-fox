package dev.pulselite;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;

/** «Смена неба»: клиентский оверлей (цветовой фильтр + градиент + звёзды/лепестки). Звук при выборе = предпросмотр. */
public final class PulseSky {
    private PulseSky() {}
    public static final String[] IDS = {"off", "sky_day", "sky_sunset", "sky_night", "sky_dawn", "sky_sakura", "sky_aurora", "sky_storm", "sky_void"};
    public static final String[] NAMES = {"Выкл (обычное)", "День", "Закат", "Ночь", "Рассвет", "Сакура", "Аврора", "Гроза", "Пустота"};
    // верх, низ (RGB), тон (RGB), сила тона 0..100, звёзды
    private static final int[][] P = {
            {0, 0, 0, 0, 0},
            {0x4FA8FF, 0xBDE6FF, 0xCFEFFF, 12, 0},
            {0x6A2C8F, 0xFF8A4C, 0xFF7A3D, 30, 0},
            {0x050824, 0x1B2A6B, 0x0A1240, 55, 1},
            {0x7A5CE0, 0xFFB6C8, 0xFFC4A0, 22, 0},
            {0xC85A9C, 0xFFD1E3, 0xFFB7D5, 24, 2},
            {0x0A2A1F, 0x2CE6A5, 0x0B2A3A, 38, 1},
            {0x10131C, 0x3A4254, 0x1A2030, 52, 0},
            {0x000000, 0x2A0E4A, 0x07030F, 62, 1}};
    private static float fade = 0f;

    public static void select(int i) {
        PulseConfig.get().skyPreset = i;
        PulseSounds.play(i == 0 ? "toggle_off" : IDS[i], 1f, 0.9f);
    }

    private static int rgba(int a, int rgb) { return (Math.max(0, Math.min(255, a)) << 24) | rgb; }

    /** Рисует оверлей на области w*h. preview=true — без проверки «виден ли небосвод». */
    public static void render(GuiGraphics g, int w, int h, int preset, float k, long ms) {
        if (preset <= 0 || preset >= P.length || k <= 0.01f) return;
        int[] p = P[preset];
        float it = PulseConfig.get().skyIntensity / 100f * k;
        g.fill(0, 0, w, h, rgba((int) (p[3] * 2.55f * it), p[2]));
        g.fillGradient(0, 0, w, (int) (h * 0.7f), rgba((int) (150 * it), p[0]), rgba(0, p[0]));
        g.fillGradient(0, (int) (h * 0.45f), w, h, rgba(0, p[1]), rgba((int) (70 * it), p[1]));
        double t = ms / 1000.0;
        if (p[4] == 1) {
            for (int i = 0; i < 70; i++) {
                int x = (int) (frac(Math.sin(i * 12.9898) * 43758.5453) * w);
                int y = (int) (frac(Math.sin(i * 78.233) * 12345.678) * h * 0.55);
                float tw = (float) (0.5 + 0.5 * Math.sin(t * 2 + i));
                g.fill(x, y, x + 1 + (i % 5 == 0 ? 1 : 0), y + 1 + (i % 5 == 0 ? 1 : 0), rgba((int) (200 * tw * it), 0xFFFFFF));
            }
        } else if (p[4] == 2) {
            for (int i = 0; i < 24; i++) {
                int x = (int) ((frac(i * 0.37) * w + Math.sin(t * 0.8 + i) * 18 + t * 12) % (w + 20));
                int y = (int) ((frac(i * 0.71) * h + t * (18 + i % 7 * 4)) % (h + 20));
                g.fill(x, y, x + 3, y + 2, rgba((int) (200 * it), 0xFFB7D5));
            }
        }
        if (preset == 6) {
            for (int x = 0; x < w; x += 4) {
                double a = 0.5 + 0.5 * Math.sin(t * 0.8 + x * 0.02) * Math.sin(t * 0.5 + x * 0.007);
                g.fillGradient(x, (int) (h * 0.05), x + 4, (int) (h * (0.25 + 0.15 * a)), rgba(0, 0x2CE6A5), rgba((int) (90 * a * it), 0x2CE6A5));
            }
        }
        if (preset == 7 && (ms / 100) % 53 == 0) g.fill(0, 0, w, h, rgba((int) (120 * it), 0xFFFFFF));
    }

    private static double frac(double d) { return d - Math.floor(d); }

    /** Для HUD: плавно появляется только когда над головой открытое небо. */
    public static void hud(GuiGraphics g, Minecraft mc) {
        int pr = PulseConfig.get().skyPreset;
        if (pr <= 0 || mc.player == null || mc.level == null) return;
        boolean open;
        try { open = mc.level.canSeeSky(mc.player.blockPosition()); } catch (Throwable t) { open = true; }
        fade = Gfx.approach(fade, open ? 1f : 0.25f, 0.04f);
        render(g, mc.getWindow().getGuiScaledWidth(), mc.getWindow().getGuiScaledHeight(), pr, fade, System.currentTimeMillis());
    }
}
