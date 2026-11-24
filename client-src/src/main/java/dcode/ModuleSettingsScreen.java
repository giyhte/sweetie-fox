package dcode;

import dcode.module.Module;
import dcode.setting.BoolSetting;
import dcode.setting.ModeSetting;
import dcode.setting.NumSetting;
import dcode.setting.Setting;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.client.gui.widget.SliderWidget;
import net.minecraft.text.Text;

public class ModuleSettingsScreen extends Screen {
    private final Screen parent;
    private final Module module;

    public ModuleSettingsScreen(Screen parent, Module module) {
        super(Text.literal(module.getName()));
        this.parent = parent;
        this.module = module;
    }

    @Override
    protected void init() {
        int cx = width / 2;
        int rows = (module.getSettings().size() + 1) / 2;
        int y0 = Math.max(40, height / 2 - rows * 12 - 10);
        int i = 0;
        for (Setting s : module.getSettings()) {
            int x = (i % 2 == 0) ? cx - 160 : cx + 5;
            int y = y0 + (i / 2) * 24;
            if (s instanceof BoolSetting b) {
                addDrawableChild(ButtonWidget.builder(boolText(b), btn -> { b.toggle(); btn.setMessage(boolText(b)); })
                        .dimensions(x, y, 155, 20).build());
            } else if (s instanceof ModeSetting m) {
                addDrawableChild(ButtonWidget.builder(modeText(m), btn -> { m.cycle(); btn.setMessage(modeText(m)); })
                        .dimensions(x, y, 155, 20).build());
            } else if (s instanceof NumSetting n) {
                addDrawableChild(new NumSlider(x, y, 155, n));
            }
            i++;
        }
        addDrawableChild(ButtonWidget.builder(Text.literal("Назад"), b -> close())
                .dimensions(cx - 50, y0 + rows * 24 + 10, 100, 20).build());
    }

    private static Text boolText(BoolSetting b) { return Text.literal(b.name + ": " + (b.get() ? "ВКЛ" : "ВЫКЛ")); }
    private static Text modeText(ModeSetting m) { return Text.literal(m.name + ": " + m.get()); }

    @Override
    public void render(DrawContext ctx, int mx, int my, float delta) {
        super.render(ctx, mx, my, delta);
        ctx.drawCenteredTextWithShadow(textRenderer, module.getName() + " — настройки", width / 2, 18, 0xFFB388FF);
    }

    @Override
    public void close() { client.setScreen(parent); }

    @Override
    public void removed() { Config.save(); }

    private static class NumSlider extends SliderWidget {
        private final NumSetting s;

        NumSlider(int x, int y, int w, NumSetting s) {
            super(x, y, w, 20, Text.empty(), (s.get() - s.min) / (s.max - s.min));
            this.s = s;
            updateMessage();
        }

        @Override
        protected void updateMessage() {
            if (s != null) setMessage(Text.literal(s.name + ": " + s.format()));
        }

        @Override
        protected void applyValue() {
            s.set(s.min + value * (s.max - s.min));
            updateMessage();
        }
    }
}
