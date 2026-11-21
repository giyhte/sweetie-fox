package dev.pulselite;

import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.multiplayer.JoinMultiplayerScreen;
import net.minecraft.client.gui.screens.options.OptionsScreen;
import net.minecraft.client.gui.screens.worldselection.SelectWorldScreen;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.util.ArrayList;
import java.util.List;

/** Главное меню: арт-фон с параллаксом, лепестки, логотип, анимированные кнопки с иконками и звуками. */
public class PulseTitleScreen extends Screen {
    private static boolean welcomed = false;
    private final List<String> labels = new ArrayList<>();
    private final List<String> icons = new ArrayList<>();
    private final List<Runnable> actions = new ArrayList<>();
    private float[] hov;
    private int lastHover = -1, sel = -1;
    private int bx, by, bw = 190, bh = 24, gap = 5;
    private long opened;

    public PulseTitleScreen() { super(Component.literal("Sweetie Fox")); }

    private void add(String l, String ic, Runnable r) { labels.add(l); icons.add(ic); actions.add(r); }

    @Override
    protected void init() {
        labels.clear(); icons.clear(); actions.clear();
        add("Одиночная игра", "play", () -> minecraft.setScreen(new SelectWorldScreen(this)));
        add("Сетевая игра", "globe", () -> minecraft.setScreen(new JoinMultiplayerScreen(this)));
        add("Sweetie Fox Menu", "bolt", () -> minecraft.setScreen(new PulseMenuScreen(this)));
        add("Настройки", "gear", () -> minecraft.setScreen(new OptionsScreen(this, minecraft.options)));
        add("Выход", "power", () -> minecraft.stop());
        hov = new float[labels.size()];
        bw = Math.min(190, width / 2 - 20);
        int total = labels.size() * (bh + gap) - gap;
        bx = Math.max(16, width / 12);
        by = Math.max(70, height / 2 - total / 2 + 22);
        if (by + total > height - 22) by = height - 22 - total;
        opened = System.currentTimeMillis();
        if (!welcomed) { welcomed = true; PulseSounds.ui("title_start"); }
    }

    @Override
    public boolean shouldCloseOnEsc() { return false; }

    private int btnX(int i, long t) {
        float k = Math.min(1f, Math.max(0f, (t - opened - i * 70L) / 350f));
        k = 1 - (1 - k) * (1 - k) * (1 - k);
        return (int) (bx - (1 - k) * (bw + 30)) + (int) (hov[i] * 10);
    }

    @Override
    public void render(GuiGraphics g, int mx, int my, float pt) {
        PulseConfig c = PulseConfig.get();
        long now = System.currentTimeMillis();
        double time = now / 1000.0;
        // фон с параллаксом
        int pad = 14;
        int ox = (int) ((mx - width / 2.0) / width * -pad), oy = (int) ((my - height / 2.0) / height * -pad / 2);
        Identifier bg = Gfx.id("textures/gui/bg/scene_" + Math.floorMod(c.menuPreset, PulseTheme.NAMES.length) + ".png");
        g.blit(RenderPipelines.GUI_TEXTURED, bg, -pad + ox, -pad + oy, 0f, 0f, width + pad * 2, height + pad * 2, 1920, 1080, 1920, 1080);
        g.fillGradient(0, 0, width * 2 / 3, height, 0xAA05030F, 0x00000000);
        g.fillGradient(0, height * 3 / 4, width, height, 0x00000000, 0xAA000000);
        // лепестки
        if (c.petals) {
            Identifier petal = Gfx.id("textures/gui/petal.png");
            for (int i = 0; i < 26; i++) {
                double s1 = frac(Math.sin(i * 12.9898) * 43758.5453), s2 = frac(Math.sin(i * 78.233) * 12345.678);
                float x = (float) ((s1 * (width + 40) + time * (10 + s2 * 14) + Math.sin(time * 0.9 + i) * 16) % (width + 40)) - 20;
                float y = (float) ((s2 * (height + 40) + time * (16 + s1 * 18)) % (height + 40)) - 20;
                g.pose().pushMatrix();
                g.pose().translate(x, y);
                g.pose().rotate((float) (time * (0.6 + s1) + i));
                g.blit(RenderPipelines.GUI_TEXTURED, petal, -5, -5, 0f, 0f, 10, 10, 32, 32, 32, 32);
                g.pose().popMatrix();
            }
        }
        // логотип
        int lw = Math.min(260, width / 2 - 10), lh = lw / 4;
        int ly = Math.max(8, by - lh - 14) + (int) (Math.sin(time * 1.6) * 2);
        g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/logo.png"), bx - 10, ly, 0f, 0f, lw, lh, 768, 192, 768, 192);
        // кнопки
        int accent = PulseTheme.accent(c.menuPreset) & 0xFFFFFF;
        int hover = -1;
        for (int i = 0; i < labels.size(); i++) {
            int x = btnX(i, now), y = by + i * (bh + gap);
            boolean h = Gfx.in(mx, my, x, y, bw, bh) || sel == i;
            if (h) hover = i;
            hov[i] = Gfx.approach(hov[i], h ? 1f : 0f, 0.25f);
            int w = bw + (int) (hov[i] * 14);
            Gfx.rr(g, x, y, w, bh, Gfx.argb(0x66 + (int) (hov[i] * 0x44), h ? accent : 0x0B0820));
            Gfx.border(g, x, y, w, bh, Gfx.argb(0x70 + (int) (hov[i] * 0x8F), 0xFFFFFF));
            g.fill(x + 1, y + 4, x + 3, y + bh - 4, Gfx.argb((int) (255 * hov[i]), 0xFFFFFF));
            Gfx.icon(g, icons.get(i), x + 8, y + 5 - (int) (hov[i] * 1), 14);
            Gfx.text(g, labels.get(i), x + 28, y + (bh - 8) / 2, 0xFFFFFFFF);
        }
        if (hover != lastHover) { if (hover >= 0) PulseSounds.ui("ui_hover"); lastHover = hover; }
        { int fw = Math.min(150, width / 4), fh = fw * 131 / 145; g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/fox_sleep.png"), width - fw - 12, height - fh - 8 + (int) (Math.sin(time * 1.4) * 2), 0f, 0f, fw, fh, 145, 131, 145, 131); }
        Gfx.text(g, "Right Shift — меню Sweetie Fox в игре", 8, height - 12, 0xAAFFFFFF);
        String nick = minecraft.getUser().getName();
        int nw = Gfx.width(nick) + 18;
        Gfx.rr(g, width - nw - 8, 8, nw, 14, 0x88000000);
        g.fill(width - nw - 3, 13, width - nw + 1, 17, 0xFF000000 | accent);
        Gfx.text(g, nick, width - nw + 5, 11, 0xFFFFFFFF);
    }

    private static double frac(double d) { return d - Math.floor(d); }

    @Override
    public boolean mouseClicked(MouseButtonEvent e, boolean dbl) {
        if (e.button() == 0) {
            for (int i = 0; i < labels.size(); i++) {
                if (Gfx.in(e.x(), e.y(), btnX(i, System.currentTimeMillis()), by + i * (bh + gap), bw, bh)) {
                    PulseSounds.ui("ui_click");
                    actions.get(i).run();
                    return true;
                }
            }
        }
        return super.mouseClicked(e, dbl);
    }

    @Override
    public boolean keyPressed(KeyEvent e) {
        int k = e.key();
        int n = labels.size();
        if (k == 264) { sel = (sel + 1) % n; return true; }            // вниз
        if (k == 265) { sel = sel <= 0 ? n - 1 : sel - 1; return true; } // вверх
        if ((k == 257 || k == 335) && sel >= 0) { PulseSounds.ui("ui_click"); actions.get(sel).run(); return true; }
        return super.keyPressed(e);
    }
}
