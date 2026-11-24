package dcode;

import dcode.module.Category;
import dcode.module.Module;
import dcode.module.ModuleManager;
import dcode.setting.BoolSetting;
import dcode.setting.ModeSetting;
import dcode.setting.NumSetting;
import dcode.setting.Setting;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.util.InputUtil;
import net.minecraft.text.Text;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Компактное меню DCODE в стиле лаунчера: категории, карточки модулей, бинды, настройки, профиль. */
public class DcodeScreen extends Screen {
    private static final int BG = 0xF012091F, SIDE = 0xFF0D0719, CARD = 0xFF1A1136, CARD_H = 0xFF241949;
    private static final int ACC = 0xFFA855F7, OFF = 0xFF3A2D5C, TXT = 0xFFFFFFFF, DIM = 0xFF8B7BB8;
    private static final int SIDE_W = 88, CARD_HEIGHT = 38, GAP = 6, ROW = 24;

    private int px, py, pw, ph, cx, cy, cw, ch;
    private int cat = -1;                 // -1 = все
    private boolean profile;
    private String search = "", nickText = "", status = "";
    private Module open, binding;
    private int focus = 1;                // 0 нет, 1 поиск, 2 ник
    private double scroll;
    private int maxScroll;
    private NumSetting dragging;
    private int dragX, dragW;
    private final Map<Module, Float> anim = new HashMap<>();

    public DcodeScreen() { super(Text.literal("DCODE")); }

    @Override
    protected void init() {
        pw = Math.min(420, width - 16);
        ph = Math.min(260, height - 16);
        px = (width - pw) / 2;
        py = (height - ph) / 2;
        cx = px + SIDE_W + 6;
        cy = py + 30;
        cw = pw - SIDE_W - 12;
        ch = ph - 30 - 16;
        nickText = Profile.nick();
    }

    // ---------- вспомогательное рисование ----------
    private static void rrect(DrawContext c, int x, int y, int w, int h, int r, int col) {
        r = Math.min(r, Math.min(w, h) / 2);
        c.fill(x, y + r, x + w, y + h - r, col);
        for (int i = 0; i < r; i++) {
            double d = r - i - 0.5;
            int inset = r - (int) Math.round(Math.sqrt(r * r - d * d));
            c.fill(x + inset, y + i, x + w - inset, y + i + 1, col);
            c.fill(x + inset, y + h - i - 1, x + w - inset, y + h - i, col);
        }
    }

    private static int lerp(int a, int b, float t) {
        int r = (int) (((a >> 16) & 255) + ((((b >> 16) & 255) - ((a >> 16) & 255)) * t));
        int g = (int) (((a >> 8) & 255) + ((((b >> 8) & 255) - ((a >> 8) & 255)) * t));
        int bl = (int) ((a & 255) + (((b & 255) - (a & 255)) * t));
        return 0xFF000000 | (r << 16) | (g << 8) | bl;
    }

    private void toggleSwitch(DrawContext c, int x, int y, float a) {
        rrect(c, x, y, 20, 10, 5, lerp(OFF, ACC, a));
        rrect(c, x + 1 + (int) (a * 10), y + 1, 8, 8, 4, 0xFFFFFFFF);
    }

    private void text(DrawContext c, String s, int x, int y, int col) { c.drawText(textRenderer, s, x, y, col, false); }

    private static boolean in(double mx, double my, int x, int y, int w, int h) {
        return mx >= x && mx < x + w && my >= y && my < y + h;
    }

    private static String keyName(int key) {
        return key < 0 ? "—" : InputUtil.fromKeyCode(key, 0).getLocalizedText().getString();
    }

    private List<Module> visible() {
        List<Module> out = new ArrayList<>();
        String q = search.toLowerCase();
        for (Module m : ModuleManager.all()) {
            if (cat >= 0 && m.getCategory() != Category.values()[cat]) continue;
            if (!q.isEmpty() && !m.getName().toLowerCase().contains(q) && !m.getDescription().toLowerCase().contains(q)) continue;
            out.add(m);
        }
        return out;
    }

    private int cols() { return cw >= 280 ? 2 : 1; }
    private int cardW() { return (cw - GAP * (cols() - 1)) / cols(); }
    private int cardX(int i) { return cx + (i % cols()) * (cardW() + GAP); }
    private int cardY(int i) { return cy + (i / cols()) * (CARD_HEIGHT + GAP) - (int) scroll; }

    private int catIndexAt(double mx, double my) {
        if (!in(mx, my, px + 4, py + 30, SIDE_W - 8, 16 * 5)) return -2;
        return (int) ((my - (py + 30)) / 16) - 1;   // 0 строка = «Все» (-1)
    }

    // ---------- отрисовка ----------
    @Override
    public void render(DrawContext c, int mx, int my, float delta) {
        super.render(c, mx, my, delta);
        rrect(c, px - 1, py - 1, pw + 2, ph + 2, 7, 0x55A855F7);
        rrect(c, px, py, pw, ph, 6, BG);
        rrect(c, px, py, SIDE_W, ph, 6, SIDE);
        c.fill(px + SIDE_W - 6, py, px + SIDE_W, py + ph, SIDE);

        // сайдбар
        c.drawText(textRenderer, "DCODE", px + 10, py + 10, ACC, true);
        String[] names = new String[Category.values().length + 1];
        names[0] = "Все";
        for (int i = 0; i < Category.values().length; i++) names[i + 1] = Category.values()[i].title;
        for (int i = 0; i < names.length; i++) {
            int y = py + 30 + i * 16;
            boolean sel = !profile && cat == i - 1;
            boolean hov = in(mx, my, px + 4, y, SIDE_W - 8, 14);
            if (sel || hov) rrect(c, px + 4, y, SIDE_W - 8, 14, 3, sel ? CARD_H : CARD);
            if (sel) c.fill(px + 4, y + 3, px + 6, y + 11, ACC);
            text(c, names[i], px + 12, y + 3, sel ? TXT : DIM);
        }
        // карточка профиля
        int pyc = py + ph - 34;
        rrect(c, px + 4, pyc, SIDE_W - 8, 28, 4, profile || in(mx, my, px + 4, pyc, SIDE_W - 8, 28) ? CARD_H : CARD);
        text(c, textRenderer.trimToWidth(Profile.nick(), SIDE_W - 20), px + 10, pyc + 5, TXT);
        text(c, textRenderer.trimToWidth("Лиц.: " + Profile.licenseText(), SIDE_W - 20), px + 10, pyc + 16,
                Profile.licenseOk() ? 0xFF7CFC9A : 0xFFFF6B6B);

        // заголовок страницы
        if (profile) {
            c.drawText(textRenderer, "Профиль", cx, py + 10, TXT, true);
            renderProfile(c, mx, my);
        } else if (open != null) {
            boolean hov = in(mx, my, cx, py + 6, 60, 16);
            c.drawText(textRenderer, "‹ Назад", cx, py + 10, hov ? TXT : DIM, false);
            c.drawText(textRenderer, open.getName(), cx + 64, py + 10, ACC, true);
            renderSettings(c, mx, my);
        } else {
            c.drawText(textRenderer, cat < 0 ? "Все модули" : Category.values()[cat].title, cx, py + 10, TXT, true);
            int sx = cx + cw - 110;
            rrect(c, sx, py + 6, 110, 16, 4, CARD);
            if (focus == 1) c.fill(sx, py + 21, sx + 110, py + 22, ACC);
            String shown = search.isEmpty() && focus != 1 ? "Поиск…" : textRenderer.trimToWidth(search, 98);
            text(c, shown + (focus == 1 && (System.currentTimeMillis() / 500) % 2 == 0 ? "|" : ""), sx + 6, py + 10,
                    search.isEmpty() ? DIM : TXT);
            renderList(c, mx, my);
            String hint = "ЛКМ вкл/выкл · ПКМ настройки · клик по бинду — клавиша";
            text(c, textRenderer.trimToWidth(hint, cw), cx, py + ph - 12, 0xFF5E5086);
        }
    }

    private void renderList(DrawContext c, int mx, int my) {
        List<Module> list = visible();
        int rows = (list.size() + cols() - 1) / cols();
        maxScroll = Math.max(0, rows * (CARD_HEIGHT + GAP) - GAP - ch);
        scroll = Math.max(0, Math.min(scroll, maxScroll));
        c.enableScissor(cx - 2, cy, cx + cw + 2, cy + ch);
        for (int i = 0; i < list.size(); i++) {
            Module m = list.get(i);
            int x = cardX(i), y = cardY(i), w = cardW();
            if (y + CARD_HEIGHT < cy || y > cy + ch) continue;
            boolean hov = in(mx, my, x, y, w, CARD_HEIGHT) && in(mx, my, cx, cy, cw, ch);
            rrect(c, x, y, w, CARD_HEIGHT, 5, hov ? CARD_H : CARD);
            float a = anim.getOrDefault(m, m.isEnabled() ? 1f : 0f);
            a += ((m.isEnabled() ? 1f : 0f) - a) * 0.3f;
            anim.put(m, a);
            toggleSwitch(c, x + w - 26, y + 6, a);
            text(c, m.getName(), x + 6, y + 5, TXT);
            text(c, textRenderer.trimToWidth(m.getDescription(), w - 12), x + 6, y + 16, DIM);
            String b = binding == m ? "Нажми клавишу…" : "Бинд: " + keyName(m.getKey());
            text(c, b, x + 6, y + 27, binding == m ? ACC : 0xFF6F5FA0);
        }
        c.disableScissor();
    }

    private void renderSettings(DrawContext c, int mx, int my) {
        List<Setting> st = open.getSettings();
        maxScroll = Math.max(0, (st.size() + 1) * ROW - ch);
        scroll = Math.max(0, Math.min(scroll, maxScroll));
        int sx = cx + cw - 124;
        c.enableScissor(cx - 2, cy, cx + cw + 2, cy + ch);
        for (int i = 0; i <= st.size(); i++) {
            int y = cy + i * ROW - (int) scroll;
            if (y + ROW < cy || y > cy + ch) continue;
            rrect(c, cx, y, cw, ROW - 3, 4, in(mx, my, cx, y, cw, ROW - 3) ? CARD_H : CARD);
            if (i == 0) {
                text(c, "Бинд", cx + 8, y + 6, TXT);
                rrect(c, sx, y + 3, 116, 15, 3, 0xFF120B26);
                String b = binding == open ? "Нажми клавишу…" : "[" + keyName(open.getKey()) + "]";
                text(c, b, sx + 58 - textRenderer.getWidth(b) / 2, y + 7, binding == open ? ACC : TXT);
                continue;
            }
            Setting s = st.get(i - 1);
            text(c, textRenderer.trimToWidth(s.name, sx - cx - 12), cx + 8, y + 6, TXT);
            if (s instanceof BoolSetting b) {
                toggleSwitch(c, sx + 96, y + 5, b.get() ? 1f : 0f);
            } else if (s instanceof ModeSetting m) {
                rrect(c, sx, y + 3, 116, 15, 3, 0xFF120B26);
                text(c, m.get(), sx + 58 - textRenderer.getWidth(m.get()) / 2, y + 7, ACC);
            } else if (s instanceof NumSetting n) {
                float r = (float) ((n.get() - n.min) / (n.max - n.min));
                rrect(c, sx, y + 9, 80, 4, 2, OFF);
                rrect(c, sx, y + 9, Math.max(4, (int) (80 * r)), 4, 2, ACC);
                rrect(c, sx + (int) (76 * r), y + 6, 6, 10, 3, 0xFFFFFFFF);
                text(c, n.format(), sx + 86, y + 7, DIM);
            }
        }
        c.disableScissor();
    }

    private void renderProfile(DrawContext c, int mx, int my) {
        String nick = Profile.nick();
        rrect(c, cx, cy, 32, 32, 16, ACC);
        String ch0 = nick.isEmpty() ? "D" : nick.substring(0, 1).toUpperCase();
        c.drawText(textRenderer, ch0, cx + 16 - textRenderer.getWidth(ch0) / 2, cy + 12, TXT, true);
        c.drawText(textRenderer, nick, cx + 40, cy + 5, TXT, true);
        text(c, "Аккаунт: " + (Profile.account.isEmpty() ? "—" : Profile.account), cx + 40, cy + 18, DIM);
        text(c, "Лицензия: " + Profile.licenseText(), cx, cy + 44, Profile.licenseOk() ? 0xFF7CFC9A : 0xFFFF6B6B);
        text(c, "Ник в игре", cx, cy + 66, DIM);
        rrect(c, cx, cy + 78, 150, 18, 4, CARD);
        if (focus == 2) c.fill(cx, cy + 95, cx + 150, cy + 96, ACC);
        text(c, nickText + (focus == 2 && (System.currentTimeMillis() / 500) % 2 == 0 ? "|" : ""), cx + 6, cy + 83, TXT);
        boolean hov = in(mx, my, cx + 158, cy + 78, 80, 18);
        rrect(c, cx + 158, cy + 78, 80, 18, 4, hov ? 0xFF8B3FE0 : 0xFF6D28D9);
        text(c, "Сменить ник", cx + 198 - textRenderer.getWidth("Сменить ник") / 2, cy + 83, TXT);
        if (!status.isEmpty()) text(c, status, cx, cy + 104, 0xFFCDBDF7);
    }

    // ---------- ввод ----------
    @Override
    public boolean mouseClicked(double mx, double my, int button) {
        if (binding != null) { binding = null; return true; }

        int ci = catIndexAt(mx, my);
        if (ci >= -1) { cat = ci; profile = false; open = null; scroll = 0; focus = 1; return true; }
        if (in(mx, my, px + 4, py + ph - 34, SIDE_W - 8, 28)) { profile = true; open = null; focus = 2; return true; }

        if (profile) {
            if (in(mx, my, cx + 158, cy + 78, 80, 18)) {
                status = NickChanger.change(nickText) ? "Ник изменён — перезайди на сервер" : "Ник: 3–16 символов, A–Z, 0–9, _";
            } else focus = in(mx, my, cx, cy + 78, 150, 18) ? 2 : 0;
            return true;
        }

        if (open != null) {
            if (in(mx, my, cx, py + 6, 60, 16)) { open = null; scroll = 0; focus = 1; return true; }
            if (!in(mx, my, cx, cy, cw, ch)) return true;
            int i = (int) ((my - cy + scroll) / ROW);
            List<Setting> st = open.getSettings();
            if (i < 0 || i > st.size()) return true;
            int rowTop = cy + i * ROW - (int) scroll;
            if (my > rowTop + ROW - 3) return true;
            int sx = cx + cw - 124;
            if (i == 0) { if (mx >= sx) binding = open; return true; }
            Setting s = st.get(i - 1);
            if (s instanceof BoolSetting b) { b.toggle(); Config.save(); }
            else if (s instanceof ModeSetting m) { m.cycle(); Config.save(); }
            else if (s instanceof NumSetting n && mx >= sx - 4 && mx <= sx + 84) {
                dragging = n; dragX = sx; dragW = 80;
                mouseDragged(mx, my, button, 0, 0);
            }
            return true;
        }

        // список модулей
        int sx = cx + cw - 110;
        if (in(mx, my, sx, py + 6, 110, 16)) { focus = 1; return true; }
        if (!in(mx, my, cx, cy, cw, ch)) return super.mouseClicked(mx, my, button);
        List<Module> list = visible();
        for (int i = 0; i < list.size(); i++) {
            Module m = list.get(i);
            int x = cardX(i), y = cardY(i), w = cardW();
            if (!in(mx, my, x, y, w, CARD_HEIGHT)) continue;
            if (in(mx, my, x + 4, y + 25, 110, 11)) binding = m;
            else if (button == 1) { open = m; scroll = 0; focus = 0; }
            else { m.toggle(); Config.save(); }
            return true;
        }
        return true;
    }

    @Override
    public boolean mouseDragged(double mx, double my, int button, double dx, double dy) {
        if (dragging != null) {
            double r = Math.max(0, Math.min(1, (mx - dragX) / dragW));
            dragging.set(dragging.min + r * (dragging.max - dragging.min));
            return true;
        }
        return super.mouseDragged(mx, my, button, dx, dy);
    }

    @Override
    public boolean mouseReleased(double mx, double my, int button) {
        if (dragging != null) { dragging = null; Config.save(); return true; }
        return super.mouseReleased(mx, my, button);
    }

    @Override
    public boolean mouseScrolled(double mx, double my, double h, double v) {
        scroll = Math.max(0, Math.min(maxScroll, scroll - v * 14));
        return true;
    }

    @Override
    public boolean keyPressed(int key, int scan, int mods) {
        if (binding != null) {
            if (key == GLFW.GLFW_KEY_DELETE || key == GLFW.GLFW_KEY_BACKSPACE) binding.setKey(-1);
            else if (key != GLFW.GLFW_KEY_ESCAPE) binding.setKey(key);
            binding = null;
            Config.save();
            return true;
        }
        if (key == GLFW.GLFW_KEY_BACKSPACE) {
            if (focus == 1 && !search.isEmpty()) { search = search.substring(0, search.length() - 1); scroll = 0; return true; }
            if (focus == 2 && !nickText.isEmpty()) { nickText = nickText.substring(0, nickText.length() - 1); return true; }
        }
        return super.keyPressed(key, scan, mods);
    }

    @Override
    public boolean charTyped(char chr, int mods) {
        if (binding != null) return true;
        if (focus == 1 && chr >= 32 && search.length() < 24) { search += chr; scroll = 0; return true; }
        if (focus == 2 && nickText.length() < 16 && (Character.isLetterOrDigit(chr) && chr < 128 || chr == '_')) { nickText += chr; return true; }
        return super.charTyped(chr, mods);
    }

    @Override
    public void removed() { Config.save(); }

    @Override
    public boolean shouldPause() { return false; }
}
