package dcode.module;

import dcode.Profile;
import dcode.setting.BoolSetting;
import dcode.setting.ModeSetting;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;

import java.awt.Color;
import java.util.ArrayList;
import java.util.List;

public class Hud extends Module {
    private final BoolSetting watermark = add(new BoolSetting("Ватермарк", true));
    private final BoolSetting arraylist = add(new BoolSetting("Список модулей", true));
    private final BoolSetting info = add(new BoolSetting("Координаты", true));
    private final ModeSetting theme = add(new ModeSetting("Тема", 0, "Фиолетовая", "Голубая", "Радуга"));

    private static Hud instance;

    public Hud() {
        super("HUD");
        instance = this;
        setEnabled(true);
        HudRenderCallback.EVENT.register(this::render);
    }

    public static int accent(float offset) {
        int t = instance == null ? 0 : instance.theme.index();
        if (t == 1) return 0xFF4DD0E1;
        if (t == 2) return Color.HSBtoRGB((System.currentTimeMillis() % 4000L) / 4000f + offset, 0.6f, 1f) | 0xFF000000;
        return 0xFFB388FF;
    }

    private void render(DrawContext ctx, net.minecraft.client.render.RenderTickCounter tick) {
        if (!isEnabled() || mc.options.hudHidden || mc.player == null) return;
        TextRenderer tr = mc.textRenderer;
        int bg = 0xAA101018;

        if (watermark.get()) {
            String s = "DCODE  |  " + Profile.nick() + "  |  " + mc.getCurrentFps() + " FPS  |  лицензия: " + Profile.licenseText();
            int w = tr.getWidth(s);
            ctx.fill(6, 6, 6 + w + 10, 22, bg);
            ctx.fill(6, 6, 8, 22, accent(0));
            ctx.drawTextWithShadow(tr, s, 12, 10, 0xFFFFFFFF);
        }

        if (arraylist.get()) {
            List<Module> on = new ArrayList<>();
            for (Module m : ModuleManager.all()) if (m.isEnabled() && m != this) on.add(m);
            on.sort((a, b) -> tr.getWidth(b.getName()) - tr.getWidth(a.getName()));
            int sw = ctx.getScaledWindowWidth();
            int y = 6;
            int i = 0;
            for (Module m : on) {
                int w = tr.getWidth(m.getName());
                ctx.fill(sw - w - 10, y, sw - 4, y + 12, bg);
                ctx.fill(sw - 4, y, sw - 2, y + 12, accent(i * 0.08f));
                ctx.drawTextWithShadow(tr, m.getName(), sw - w - 7, y + 2, accent(i * 0.08f));
                y += 12;
                i++;
            }
        }

        if (info.get()) {
            String s = String.format("XYZ: %.0f %.0f %.0f", mc.player.getX(), mc.player.getY(), mc.player.getZ());
            int h = ctx.getScaledWindowHeight();
            ctx.fill(6, h - 22, 6 + tr.getWidth(s) + 10, h - 6, bg);
            ctx.fill(6, h - 22, 8, h - 6, accent(0.3f));
            ctx.drawTextWithShadow(tr, s, 12, h - 18, 0xFFFFFFFF);
        }
    }
}
