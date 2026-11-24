package dcode;

import dcode.module.Module;
import dcode.module.ModuleManager;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.client.gui.widget.TextFieldWidget;
import net.minecraft.text.Text;

import java.util.List;

public class DcodeScreen extends Screen {
    private TextFieldWidget nickField;
    private String status = "";

    public DcodeScreen() { super(Text.literal("DCODE")); }

    @Override
    protected void init() {
        int cx = width / 2;
        int y0 = Math.max(70, height / 2 - 60);
        List<Module> mods = ModuleManager.all();
        for (int i = 0; i < mods.size(); i++) {
            Module m = mods.get(i);
            int x = (i % 2 == 0) ? cx - 170 : cx + 5;
            int y = y0 + (i / 2) * 24;
            addDrawableChild(ButtonWidget.builder(label(m), b -> { m.toggle(); b.setMessage(label(m)); Config.save(); })
                    .dimensions(x, y, 110, 20).build());
            ButtonWidget gear = ButtonWidget.builder(Text.literal("Настр."),
                    b -> client.setScreen(new ModuleSettingsScreen(this, m))).dimensions(x + 112, y, 53, 20).build();
            gear.active = !m.getSettings().isEmpty();
            addDrawableChild(gear);
        }
        int ny = y0 + ((mods.size() + 1) / 2) * 24 + 12;
        nickField = new TextFieldWidget(textRenderer, cx - 100, ny, 130, 20, Text.literal("Ник"));
        nickField.setMaxLength(16);
        nickField.setText(Profile.nick());
        addDrawableChild(nickField);
        addDrawableChild(ButtonWidget.builder(Text.literal("Сменить ник"), b ->
                status = NickChanger.change(nickField.getText())
                        ? "Ник изменён (перезайди на сервер)" : "Ник: 3-16 символов, A-Z 0-9 _")
                .dimensions(cx + 35, ny, 65, 20).build());
    }

    private static Text label(Module m) {
        return Text.literal(m.getName() + ": " + (m.isEnabled() ? "ВКЛ" : "ВЫКЛ"));
    }

    @Override
    public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        super.render(ctx, mouseX, mouseY, delta);
        int cx = width / 2;
        int top = Math.max(70, height / 2 - 60);
        ctx.drawCenteredTextWithShadow(textRenderer, "DCODE", cx, top - 56, dcode.module.Hud.accent(0));
        ctx.fill(cx - 170, top - 44, cx + 170, top - 43, dcode.module.Hud.accent(0.2f));
        String acc = Profile.account.isEmpty() ? "—" : Profile.account;
        ctx.drawCenteredTextWithShadow(textRenderer, "Профиль: " + Profile.nick() + "   |   Аккаунт: " + acc, cx, top - 36, 0xFFFFFFFF);
        ctx.drawCenteredTextWithShadow(textRenderer, "Лицензия: " + Profile.licenseText(), cx, top - 24,
                Profile.licenseOk() ? 0xFF7CFC9A : 0xFFFF6B6B);
        if (!status.isEmpty()) ctx.drawCenteredTextWithShadow(textRenderer, status, cx, height - 20, 0xFFFFFFFF);
    }

    @Override
    public void removed() { Config.save(); }

    @Override
    public boolean shouldPause() { return false; }
}
