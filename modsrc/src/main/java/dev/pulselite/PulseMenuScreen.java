package dev.pulselite;

import net.minecraft.client.CloudStatus;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Options;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ParticleStatus;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import java.util.function.IntConsumer;
import java.util.function.IntSupplier;
import java.util.function.Supplier;

/** Меню Sweetie Fox: верхняя панель + категории + список модулей + карточка модуля с лисёнком. */
public class PulseMenuScreen extends Screen {
    private static final String[] CATS = {"Все моды", "PvP", "Рендер", "Полезные", "Декор", "Геймплей", "Разное"};
    private static final String[] CAT_ICONS = {"gear", "combat", "visual", "bolt", "theme", "game", "info"};
    private static final String[] TOPS = {"Моды", "Популярные", "Топ"};
    private static final String[] TOP_ICONS = {"gear", "star", "bolt"};
    private static final String[] PCT = {"20%", "40%", "60%", "80%", "100%"};

    enum K { TOGGLE, STEP, ACTION, NOTE }

    static final class Row {
        K k;
        String name = "", desc = "", icon = "gear", cat = "Разное", version = "1.0.0";
        boolean popular, top;
        BooleanSupplier get;
        Consumer<Boolean> set;
        String[] opts;
        IntSupplier idx;
        IntConsumer setIdx;
        Runnable act;
        Supplier<List<Row>> settings;
        float hov, anim = -1;
    }

    // ------------------------------------------------------------ конструкторы строк
    private static Row tog(String n, String d, String ic, String cat, BooleanSupplier g, Consumer<Boolean> s) {
        Row r = new Row(); r.k = K.TOGGLE; r.name = n; r.desc = d; r.icon = ic; r.cat = cat; r.get = g; r.set = s; return r;
    }
    private static Row tog(String n, BooleanSupplier g, Consumer<Boolean> s) { return tog(n, "", "gear", "", g, s); }
    private static Row step(String n, String[] o, IntSupplier g, IntConsumer s) {
        Row r = new Row(); r.k = K.STEP; r.name = n; r.opts = o; r.idx = g; r.setIdx = s; return r;
    }
    private static Row stepInts(String n, int[] vals, IntSupplier cur, IntConsumer set, String suf) {
        String[] o = new String[vals.length];
        for (int i = 0; i < vals.length; i++) o[i] = vals[i] + suf;
        return step(n, o, () -> {
            int c = cur.getAsInt(), b = 0;
            for (int i = 0; i < vals.length; i++) if (Math.abs(vals[i] - c) < Math.abs(vals[b] - c)) b = i;
            return b;
        }, i -> set.accept(vals[i]));
    }
    private static Row act(String n, Runnable r) { Row x = new Row(); x.k = K.ACTION; x.name = n; x.act = r; return x; }
    private static Row note(String t) { Row x = new Row(); x.k = K.NOTE; x.name = t; return x; }
    private static Row module(String n, String d, String ic, String cat, Supplier<List<Row>> st) {
        Row x = new Row(); x.k = K.ACTION; x.name = n; x.desc = d; x.icon = ic; x.cat = cat; x.settings = st; return x;
    }
    private static Row pop(Row r, boolean top) { r.popular = true; r.top = top; return r; }
    private static Row withSet(Row r, Supplier<List<Row>> s) { r.settings = s; return r; }

    // ------------------------------------------------------------ состояние
    private final Screen parent;
    private final List<Row> modules = new ArrayList<>();
    private List<Row> settingsRows = new ArrayList<>();
    private Row selected;
    private boolean inSettings;
    private int cat = 0, topTab = 0;
    private String query = "";
    private EditBox search;
    private float scroll, scrollTarget, contentH;
    private String toast = "";
    private long toastUntil;
    private Row lastHover;
    private int px, py, pw, ph, sx, sy, sw, lx, ly, lw, lh, dx, dy, dw, dh;

    public PulseMenuScreen(Screen parent) {
        super(Component.literal("Sweetie Fox"));
        this.parent = parent;
    }

    private Options o() { return Minecraft.getInstance().options; }
    private void say(String s) { toast = s; toastUntil = System.currentTimeMillis() + 1800; }
    private int accent() { return 0xFF000000 | (PulseTheme.accent(PulseConfig.get().menuPreset) & 0xFFFFFF); }

    // ------------------------------------------------------------ модули
    private void build() {
        modules.clear();
        PulseConfig c = PulseConfig.get();

        modules.add(pop(withSet(tog("Звук попадания", "Аниме-звуки при ударах", "sound", "PvP", () -> c.hitSound, v -> c.hitSound = v), () -> {
            List<Row> l = new ArrayList<>();
            l.add(step("Тип звука", PulseSounds.HIT_NAMES, () -> Math.floorMod(c.hitType, 5),
                    i -> { c.hitType = i; PulseSounds.play(PulseSounds.HIT_IDS[i], 1f, c.hitVolume / 100f); }));
            l.add(act("▶ Прослушать", () -> PulseSounds.play(PulseSounds.HIT_IDS[Math.floorMod(c.hitType, 5)], 1f, c.hitVolume / 100f)));
            l.add(step("Громкость", PCT, () -> Math.max(0, Math.min(4, c.hitVolume / 20 - 1)), i -> c.hitVolume = (i + 1) * 20));
            l.add(tog("Звук крита", () -> c.critSound, v -> c.critSound = v));
            l.add(tog("Звук убийства", () -> c.killSound, v -> c.killSound = v));
            l.add(tog("Звук получения урона", () -> c.hurtSound, v -> c.hurtSound = v));
            l.add(note("Звуки синтезированы. Свои .ogg — в assets/pulselite/sounds"));
            return l;
        }), true));

        modules.add(pop(tog("Авто-спринт", "Бежишь вперёд — спринт сам", "game", "Геймплей", () -> c.autoSprint, v -> c.autoSprint = v), true));

        modules.add(pop(withSet(tog("Трекер ивентов", "FunTime: метка и список", "event", "Полезные", () -> c.eventTracker, v -> c.eventTracker = v), () -> {
            List<Row> l = new ArrayList<>();
            l.add(tog("Список ивентов", () -> c.eventList, v -> c.eventList = v));
            l.add(step("Угол списка", new String[]{"Лево-верх", "Право-верх", "Лево-низ", "Право-низ"}, () -> c.eventCorner, i -> c.eventCorner = i));
            l.add(step("Стиль списка", new String[]{"Карточки", "Компакт"}, () -> c.eventStyle, i -> c.eventStyle = i));
            l.add(step("Макс. в списке", new String[]{"1", "2", "3", "4", "5", "6"}, () -> Math.max(0, Math.min(5, c.eventMax - 1)), i -> c.eventMax = i + 1));
            l.add(tog("Показывать координаты", () -> c.eventCoords, v -> c.eventCoords = v));
            l.add(tog("Метка в мире", () -> c.eventMarker, v -> c.eventMarker = v));
            l.add(step("Стиль метки", new String[]{"Ромб + название", "Только дистанция"}, () -> c.eventMarkerStyle, i -> c.eventMarkerStyle = i));
            l.add(tog("Звук при появлении", () -> c.eventSound, v -> c.eventSound = v));
            l.add(step("Метка живёт", new String[]{"2 мин", "5 мин", "10 мин", "20 мин"},
                    () -> c.eventTimeout <= 120 ? 0 : c.eventTimeout <= 300 ? 1 : c.eventTimeout <= 600 ? 2 : 3,
                    i -> c.eventTimeout = new int[]{120, 300, 600, 1200}[i]));
            l.add(act("Проверить (тестовая метка)", () -> {
                if (minecraft != null && minecraft.player != null) { PulseEvents.test(); say("Метка создана"); } else say("Зайди в мир");
            }));
            l.add(act("Очистить метки", () -> { PulseEvents.LIST.clear(); say("Метки очищены"); }));
            l.add(note("Ловит чат: слово-ключ + координаты."));
            l.add(note("Слова: config/pulselite.json -> eventKeywords"));
            return l;
        }), true));

        modules.add(pop(withSet(tog("Динамическое небо", "Закат, ночь, аврора…", "sky", "Рендер", () -> c.skyPreset != 0, v -> {
            if (v) PulseSky.select(c.lastSky > 0 ? c.lastSky : 1); else PulseSky.select(0);
        }), () -> {
            List<Row> l = new ArrayList<>();
            l.add(step("Небо (звук = предпросмотр)", PulseSky.NAMES, () -> c.skyPreset, i -> { PulseSky.select(i); if (i > 0) c.lastSky = i; }));
            l.add(step("Сила эффекта", PCT, () -> Math.max(0, Math.min(4, c.skyIntensity / 20 - 1)), i -> c.skyIntensity = (i + 1) * 20));
            l.add(note("Виден на фоне этого меню в игре. Клиентский фильтр:"));
            l.add(note("гаснет под крышей, время на сервере не меняется."));
            return l;
        }), true));

        modules.add(pop(withSet(tog("Зум", "Приближение на клавишу C", "visual", "Полезные", () -> c.zoom, v -> c.zoom = v), () -> {
            List<Row> l = new ArrayList<>();
            l.add(stepInts("Угол зума (FOV)", new int[]{15, 20, 30, 40, 50}, () -> c.zoomFov, v -> c.zoomFov = v, "°"));
            return l;
        }), false));

        modules.add(withSet(tog("FPS счётчик", "Кадры в секунду", "perf", "Полезные", () -> c.hudFps, v -> c.hudFps = v), this::hudRows));
        modules.add(withSet(tog("Координаты", "XYZ на экране", "event", "Полезные", () -> c.hudCoords, v -> c.hudCoords = v), this::hudRows));
        modules.add(withSet(tog("Память (ОЗУ)", "Использование памяти", "perf", "Полезные", () -> c.hudRam, v -> c.hudRam = v), this::hudRows));
        modules.add(withSet(tog("Часы", "Реальное время", "info", "Полезные", () -> c.hudTime, v -> c.hudTime = v), this::hudRows));

        modules.add(tog("Без тряски при уроне", "Камера не дёргается", "visual", "Рендер",
                () -> o().damageTiltStrength().get() == 0.0, v -> { o().damageTiltStrength().set(v ? 0.0 : 1.0); o().save(); }));
        modules.add(tog("Без FOV-эффектов", "Спринт не меняет FOV", "visual", "Рендер",
                () -> o().fovEffectScale().get() == 0.0, v -> { o().fovEffectScale().set(v ? 0.0 : 1.0); o().save(); }));
        modules.add(tog("Покачивание камеры", "Bobbing при ходьбе", "visual", "Рендер",
                () -> o().bobView().get(), v -> { o().bobView().set(v); o().save(); }));

        modules.add(module("Оптимизация графики", "Пресеты и тонкая настройка", "perf", "Рендер", this::optRows));

        modules.add(module("Тема меню", "Палитра, лепестки, градиент", "theme", "Декор", () -> {
            List<Row> l = new ArrayList<>();
            l.add(step("Палитра", PulseTheme.NAMES, () -> c.menuPreset, i -> c.menuPreset = i));
            l.add(tog("Градиентное главное меню", () -> c.customTitle, v -> c.customTitle = v));
            l.add(tog("Анимация градиента", () -> c.menuAnimated, v -> c.menuAnimated = v));
            l.add(tog("Лепестки в меню", () -> c.petals, v -> c.petals = v));
            l.add(note("Палитра красит меню и акценты HUD."));
            return l;
        }));
        modules.add(withSet(tog("Звуки интерфейса", "Звуки меню и кнопок", "sound", "Декор", () -> c.uiSounds, v -> c.uiSounds = v), () -> {
            List<Row> l = new ArrayList<>();
            l.add(step("Громкость меню", PCT, () -> Math.max(0, Math.min(4, c.uiVolume / 20 - 1)), i -> c.uiVolume = (i + 1) * 20));
            return l;
        }));
        modules.add(module("Информация", "Клавиши и сброс настроек", "info", "Разное", () -> {
            List<Row> l = new ArrayList<>();
            l.add(note("Right Shift — открыть это меню"));
            l.add(note("C (зажать) — зум, клавиши в Управлении"));
            l.add(note("Конфиг: config/pulselite.json"));
            l.add(act("Сбросить настройки", () -> { PulseConfig.reset(); say("Сброшено"); }));
            return l;
        }));
        selected = modules.get(0);
    }

    private List<Row> hudRows() {
        PulseConfig c = PulseConfig.get();
        List<Row> l = new ArrayList<>();
        l.add(tog("Счётчик FPS", () -> c.hudFps, v -> c.hudFps = v));
        l.add(tog("Координаты", () -> c.hudCoords, v -> c.hudCoords = v));
        l.add(tog("Память (ОЗУ)", () -> c.hudRam, v -> c.hudRam = v));
        l.add(tog("Часы", () -> c.hudTime, v -> c.hudTime = v));
        l.add(tog("Подложка HUD", () -> c.hudBackground, v -> c.hudBackground = v));
        l.add(step("Угол HUD", new String[]{"Лево-верх", "Право-верх", "Лево-низ", "Право-низ"}, () -> c.hudCorner, i -> c.hudCorner = i));
        return l;
    }

    private List<Row> optRows() {
        Options o = o();
        List<Row> l = new ArrayList<>();
        l.add(act("Макс. FPS", () -> preset(0)));
        l.add(act("Баланс", () -> preset(1)));
        l.add(act("Красиво", () -> preset(2)));
        l.add(act("Как в ваниле", () -> preset(3)));
        l.add(stepInts("Прорисовка", new int[]{2, 3, 4, 6, 8, 10, 12, 16, 24, 32}, () -> o.renderDistance().get(), v -> { o.renderDistance().set(v); o.save(); }, " чанк."));
        l.add(stepInts("Симуляция", new int[]{5, 6, 8, 10, 12, 16}, () -> o.simulationDistance().get(), v -> { o.simulationDistance().set(v); o.save(); }, " чанк."));
        l.add(stepInts("Лимит FPS", new int[]{30, 60, 90, 120, 160, 200, 240, 260}, () -> o.framerateLimit().get(), v -> { o.framerateLimit().set(v); o.save(); }, ""));
        l.add(tog("VSync", () -> o.enableVsync().get(), v -> { o.enableVsync().set(v); o.save(); }));
        l.add(step("Частицы", new String[]{"Все", "Меньше", "Минимум"}, () -> {
            ParticleStatus p = o.particles().get();
            return p == ParticleStatus.ALL ? 0 : p == ParticleStatus.DECREASED ? 1 : 2;
        }, i -> { o.particles().set(i == 0 ? ParticleStatus.ALL : i == 1 ? ParticleStatus.DECREASED : ParticleStatus.MINIMAL); o.save(); }));
        l.add(step("Облака", new String[]{"Выкл", "Быстро", "Красиво"}, () -> {
            CloudStatus s = o.cloudStatus().get();
            return s == CloudStatus.OFF ? 0 : s == CloudStatus.FAST ? 1 : 2;
        }, i -> { o.cloudStatus().set(i == 0 ? CloudStatus.OFF : i == 1 ? CloudStatus.FAST : CloudStatus.FANCY); o.save(); }));
        l.add(tog("Тени сущностей", () -> o.entityShadows().get(), v -> { o.entityShadows().set(v); o.save(); }));
        l.add(stepInts("Mipmap", new int[]{0, 1, 2, 3, 4}, () -> o.mipmapLevels().get(), v -> { o.mipmapLevels().set(v); o.save(); }, ""));
        l.add(stepInts("Сглаж. биомов", new int[]{0, 1, 2, 3, 5, 7}, () -> o.biomeBlendRadius().get(), v -> { o.biomeBlendRadius().set(v); o.save(); }, ""));
        return l;
    }

    private void preset(int n) {
        Options o = o();
        int[][] iv = {{6, 5, 240, 0, 0}, {10, 8, 160, 2, 1}, {16, 12, 120, 4, 3}, {12, 12, 120, 4, 2}};
        int[] v = iv[n];
        o.renderDistance().set(v[0]);
        o.simulationDistance().set(v[1]);
        o.framerateLimit().set(v[2]);
        o.mipmapLevels().set(v[3]);
        o.biomeBlendRadius().set(v[4]);
        o.enableVsync().set(n >= 2);
        o.entityShadows().set(n >= 2);
        o.bobView().set(n >= 2);
        o.entityDistanceScaling().set(n == 0 ? 0.75 : n == 1 ? 1.0 : 1.5);
        o.particles().set(n == 0 ? ParticleStatus.MINIMAL : n == 1 ? ParticleStatus.DECREASED : ParticleStatus.ALL);
        o.cloudStatus().set(n == 0 ? CloudStatus.OFF : n == 1 ? CloudStatus.FAST : CloudStatus.FANCY);
        o.save();
        say(new String[]{"Макс. FPS применён", "Баланс применён", "Красивая графика", "Ванильные значения"}[n]);
    }

    // ------------------------------------------------------------ раскладка
    @Override
    protected void init() {
        if (modules.isEmpty()) build();
        pw = Math.min(540, width - 8);
        ph = Math.min(310, height - 8);
        px = (width - pw) / 2;
        py = (height - ph) / 2;
        sx = px + 6; sy = py + 36; sw = 96;
        dw = pw >= 430 ? 150 : 0;
        dx = px + pw - dw - 6; dy = sy;
        lx = sx + sw + 6;
        lw = (dw > 0 ? dx - 6 : px + pw - 6) - lx;
        ly = sy; lh = py + ph - 6 - ly;
        dh = py + ph - 6 - dy;
        int tabsEnd = px + 112;
        for (String t : TOPS) tabsEnd += Gfx.width(t) + 30;
        int sbx = tabsEnd + 4, sbw = px + pw - 52 - sbx;
        search = new EditBox(font, sbx, py + 8, Math.max(40, sbw), 16, Component.literal("Поиск"));
        search.setHint(Component.literal("Поиск модов..."));
        search.setMaxLength(24);
        search.setValue(query);
        search.setResponder(s -> { query = s; scrollTarget = 0; });
        addRenderableWidget(search);
    }

    private List<Row> rows() {
        if (inSettings) return settingsRows;
        List<Row> out = new ArrayList<>();
        String q = query.toLowerCase();
        for (Row r : modules) {
            if (cat > 0 && !r.cat.equals(CATS[cat])) continue;
            if (topTab == 1 && !r.popular) continue;
            if (topTab == 2 && !r.top) continue;
            if (!q.isEmpty() && !(r.name + " " + r.desc).toLowerCase().contains(q)) continue;
            out.add(r);
        }
        return out;
    }

    private int rowH(Row r) { return inSettings ? (r.k == K.NOTE ? 14 : 22) : 28; }

    private void openSettings(Row m) {
        if (m.settings == null) { say("У модуля нет настроек"); return; }
        selected = m;
        settingsRows = m.settings.get();
        inSettings = true;
        scrollTarget = 0;
        scroll = 0;
    }

    // ------------------------------------------------------------ отрисовка
    private void scaled(GuiGraphics g, String s, int x, int y, float sc, int col) {
        g.pose().pushMatrix();
        g.pose().translate((float) x, (float) y);
        g.pose().scale(sc, sc);
        Gfx.text(g, s, 0, 0, col);
        g.pose().popMatrix();
    }

    private void wrapText(GuiGraphics g, String s, int x, int y, int maxW, float sc, int col, int maxLines) {
        String[] words = s.split(" ");
        StringBuilder cur = new StringBuilder();
        int line = 0;
        for (String w : words) {
            String t = cur.length() == 0 ? w : cur + " " + w;
            if (Gfx.width(t) * sc > maxW && cur.length() > 0) {
                scaled(g, cur.toString(), x, y + line * 10, sc, col);
                line++;
                cur = new StringBuilder(w);
                if (line >= maxLines) return;
            } else cur = new StringBuilder(t);
        }
        if (cur.length() > 0 && line < maxLines) scaled(g, cur.toString(), x, y + line * 10, sc, col);
    }

    private void pill(GuiGraphics g, int x, int y, int w, int h, boolean hot, boolean strong) {
        int a = accent() & 0xFFFFFF;
        Gfx.rr(g, x, y, w, h, hot ? Gfx.argb(0xFF, a) : strong ? 0xFF3A3F9E : 0xFF1B1F52);
        Gfx.border(g, x, y, w, h, hot ? 0xFFFFFFFF : Gfx.argb(0xAA, a));
    }

    private void toggleDraw(GuiGraphics g, Row r, int x, int y) {
        boolean on = r.get.getAsBoolean();
        if (r.anim < 0) r.anim = on ? 1f : 0f;
        r.anim = Gfx.approach(r.anim, on ? 1f : 0f, 0.3f);
        int a = accent() & 0xFFFFFF;
        Gfx.rr(g, x, y, 28, 13, on ? Gfx.argb(0xFF, a) : 0xFF22254F);
        Gfx.border(g, x, y, 28, 13, 0xCCFFFFFF);
        Gfx.rr(g, x + 2 + (int) (r.anim * 15), y + 2, 9, 9, 0xFFFFFFFF);
    }

    private void spark(GuiGraphics g, int x, int y, long now, int phase) {
        float a = 0.5f + 0.5f * (float) Math.sin(now / 500.0 + phase);
        int s = 6 + (int) (a * 4);
        g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/sparkle.png"), x, y, 0f, 0f, s, s, 32, 32, 32, 32);
    }

    @Override
    public void render(GuiGraphics g, int mx, int my, float pt) {
        PulseConfig c = PulseConfig.get();
        long now = System.currentTimeMillis();
        int acc = accent(), accRgb = acc & 0xFFFFFF;
        if (minecraft != null && minecraft.level != null) {
            PulseSky.render(g, width, height, c.skyPreset, 1f, now);
            g.fill(0, 0, width, height, 0x66000010);
        } else {
            g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/bg/scene_" + Math.floorMod(c.menuPreset, 8) + ".png"),
                    0, 0, 0f, 0f, width, height, 1920, 1080, 1920, 1080);
            g.fill(0, 0, width, height, 0x88050818);
        }
        Gfx.rr(g, px, py, pw, ph, 0xF2070A26);
        g.fillGradient(px + 2, py + 2, px + pw - 2, py + ph - 2, 0x304A52D8, 0x00000000);
        Gfx.border(g, px, py, pw, ph, acc);

        // --- верхняя панель
        g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/fox_head.png"), px + 8, py + 5, 0f, 0f, 30, 21, 207, 146, 207, 146);
        scaled(g, "Sweetie", px + 42, py + 6, 1.15f, 0xFFFFFFFF);
        scaled(g, "Fox ♡", px + 42, py + 17, 1.15f, 0xFFB9A8FF);
        int tx = px + 112;
        for (int i = 0; i < TOPS.length; i++) {
            int w = Gfx.width(TOPS[i]) + 30;
            boolean h = Gfx.in(mx, my, tx, py + 6, w - 4, 20), s = topTab == i;
            pill(g, tx, py + 6, w - 4, 20, s, false);
            if (h && !s) Gfx.border(g, tx, py + 6, w - 4, 20, 0xFFFFFFFF);
            Gfx.icon(g, TOP_ICONS[i], tx + 6, py + 11, 10);
            Gfx.text(g, TOPS[i], tx + 20, py + 12, 0xFFFFFFFF);
            tx += w;
        }
        search.render(g, mx, my, pt);
        int mxb = px + pw - 46, cxb = px + pw - 24;
        pill(g, mxb, py + 8, 16, 16, Gfx.in(mx, my, mxb, py + 8, 16, 16), false);
        g.fill(mxb + 4, py + 15, mxb + 12, py + 17, 0xFFFFFFFF);
        pill(g, cxb, py + 8, 16, 16, Gfx.in(mx, my, cxb, py + 8, 16, 16), false);
        Gfx.ctext(g, "x", cxb + 8, py + 12, 0xFFFFFFFF);
        spark(g, px + pw - 68, py + 10, now, 0);
        spark(g, px + pw - 16, py + ph - 18, now, 2);
        spark(g, lx + lw - 14, ly + lh - 16, now, 4);

        // --- категории
        for (int i = 0; i < CATS.length; i++) {
            int y = sy + i * 20;
            boolean s = cat == i, h = Gfx.in(mx, my, sx, y, sw, 18);
            pill(g, sx, y, sw, 18, s, false);
            if (h && !s) Gfx.border(g, sx, y, sw, 18, 0xFFFFFFFF);
            Gfx.icon(g, CAT_ICONS[i], sx + 5, y + 4, 10);
            Gfx.text(g, CATS[i], sx + 20, y + 5, 0xFFFFFFFF);
        }
        int fy = sy + CATS.length * 20 + 2;
        int avail = py + ph - 6 - 22 - fy;
        if (avail > 34) {
            int fh = Math.min(avail, sw * 131 / 145), fw = fh * 145 / 131;
            g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/fox_sleep.png"), sx + (sw - fw) / 2, fy + avail - fh, 0f, 0f, fw, fh, 145, 131, 145, 131);
        }
        int rby = py + ph - 24;
        pill(g, sx, rby, sw, 18, Gfx.in(mx, my, sx, rby, sw, 18), false);
        Gfx.ctext(g, "Обновить", sx + sw / 2, rby + 5, 0xFFFFFFFF);

        // --- список
        List<Row> rs = rows();
        scroll = Gfx.approach(scroll, scrollTarget, 0.3f);
        Row hover = null;
        g.enableScissor(lx, ly, lx + lw, ly + lh);
        int y = ly - (int) scroll;
        int cw = lw - 8;
        if (inSettings) {
            pill(g, lx, y, cw, 18, Gfx.in(mx, my, lx, y, cw, 18), false);
            Gfx.text(g, "‹ Назад: " + (selected != null ? selected.name : ""), lx + 8, y + 5, 0xFFFFFFFF);
            y += 21;
        }
        for (Row r : rs) {
            int h = rowH(r);
            if (y + h > ly && y < ly + lh) {
                boolean in = Gfx.in(mx, my, lx, ly, lw, lh) && Gfx.in(mx, my, lx, y, cw, h);
                if (in && r.k != K.NOTE) hover = r;
                drawRow(g, r, lx, y, cw, h, in, r == selected && !inSettings, accRgb);
            }
            y += h + 3;
        }
        contentH = y - (ly - scroll);
        g.disableScissor();
        float maxS = Math.max(0, contentH - lh);
        scrollTarget = Math.max(0, Math.min(maxS, scrollTarget));
        if (maxS > 0) {
            int bh = Math.max(16, (int) (lh * lh / contentH));
            int by = ly + (int) ((lh - bh) * (scroll / maxS));
            g.fill(lx + lw - 3, ly, lx + lw - 1, ly + lh, 0x33FFFFFF);
            g.fill(lx + lw - 3, by, lx + lw - 1, by + bh, acc);
        }
        if (rs.isEmpty() && !inSettings) Gfx.ctext(g, "Ничего не найдено", lx + lw / 2, ly + 30, 0xFF9AA6E8);
        if (hover != lastHover) {
            if (hover != null) PulseSounds.ui("ui_hover");
            lastHover = hover;
        }

        if (dw > 0 && selected != null) drawDetail(g, mx, my, now, accRgb);

        if (now < toastUntil) {
            int w = Gfx.width(toast) + 16, tx2 = lx + (lw - w) / 2;
            Gfx.rr(g, tx2, ly + lh - 22, w, 16, 0xEE1B1F52);
            Gfx.border(g, tx2, ly + lh - 22, w, 16, acc);
            Gfx.ctext(g, toast, lx + lw / 2, ly + lh - 18, 0xFFFFFFFF);
        }
    }

    private void drawRow(GuiGraphics g, Row r, int x, int y, int w, int h, boolean in, boolean sel, int accRgb) {
        r.hov = Gfx.approach(r.hov, in ? 1f : 0f, 0.25f);
        if (r.k == K.NOTE) { Gfx.text(g, r.name, x + 4, y + 3, 0xFF8F9AE0); return; }
        Gfx.rr(g, x, y, w, h, Gfx.argb(0xB0 + (int) (r.hov * 0x30), sel ? 0x242A78 : 0x10143C));
        Gfx.border(g, x, y, w, h, Gfx.argb(sel ? 0xFF : 0x66 + (int) (r.hov * 0x99), accRgb));
        boolean mod = !inSettings;
        int nx = x + 8;
        if (mod) {
            Gfx.rr(g, x + 5, y + (h - 18) / 2, 18, 18, 0xFF1B2060);
            Gfx.icon(g, r.icon, x + 7, y + (h - 14) / 2, 14);
            nx = x + 30;
            Gfx.text(g, r.name, nx, y + 5, 0xFFFFFFFF);
            scaled(g, r.desc, nx, y + 16, 0.78f, 0xFF9AA6E8);
        }
        switch (r.k) {
            case TOGGLE:
                if (!mod) Gfx.text(g, r.name, nx, y + 7, 0xFFFFFFFF);
                toggleDraw(g, r, x + w - 34, y + (h - 13) / 2);
                break;
            case STEP: {
                Gfx.text(g, r.name, nx, y + 7, 0xFFFFFFFF);
                int bw = Math.min(110, w / 2 - 6), bx = x + w - bw - 5;
                String v = r.opts[Math.max(0, Math.min(r.opts.length - 1, r.idx.getAsInt()))];
                Gfx.rr(g, bx, y + 3, bw, h - 6, 0xFF1B2060);
                Gfx.text(g, "‹", bx + 4, y + 7, 0xFF000000 | accRgb);
                Gfx.text(g, "›", bx + bw - 9, y + 7, 0xFF000000 | accRgb);
                Gfx.ctext(g, v, bx + bw / 2, y + 7, 0xFFFFFFFF);
                break;
            }
            default:
                if (mod) Gfx.text(g, "›", x + w - 12, y + 10, 0xFFFFFFFF);
                else { pill(g, x, y, w, h, in, false); Gfx.ctext(g, r.name, x + w / 2, y + 7, 0xFFFFFFFF); }
        }
    }

    private void drawDetail(GuiGraphics g, int mx, int my, long now, int accRgb) {
        Gfx.rr(g, dx, dy, dw, dh, 0xC810143C);
        Gfx.border(g, dx, dy, dw, dh, Gfx.argb(0xCC, accRgb));
        int y = dy + 4;
        if (dh > 205) {
            int fw = 112, fh = 79;
            g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/fox_head.png"), dx + (dw - fw) / 2,
                    y + (int) (Math.sin(now / 700.0) * 1.5), 0f, 0f, fw, fh, 207, 146, 207, 146);
            y += fh + 4;
        }
        scaled(g, selected.name, dx + 8, y, 1.1f, 0xFFFFFFFF);
        y += 13;
        wrapText(g, selected.desc.isEmpty() ? "Настройки" : selected.desc, dx + 8, y, dw - 14, 0.85f, 0xFFB9C2FF, 2);
        y += 22;
        if (selected.k == K.TOGGLE) {
            boolean on = selected.get.getAsBoolean();
            String lab = "Статус: ";
            Gfx.text(g, lab, dx + 8, y, 0xFFB9C2FF);
            Gfx.text(g, on ? "Включён" : "Выключен", dx + 8 + Gfx.width(lab), y, on ? 0xFF6BE58D : 0xFFFF7A8A);
        } else Gfx.text(g, "Статус: Доступно", dx + 8, y, 0xFF6BE58D);
        y += 11;
        Gfx.text(g, "Версия: " + selected.version, dx + 8, y, 0xFFB9C2FF);
        y += 11;
        Gfx.text(g, "Категория: " + selected.cat, dx + 8, y, 0xFFB9C2FF);
        int by = dy + dh - 24, sy2 = by - 24;
        boolean has = selected.settings != null || inSettings;
        pill(g, dx + 6, sy2, dw - 12, 20, Gfx.in(mx, my, dx + 6, sy2, dw - 12, 20) && has, false);
        Gfx.ctext(g, inSettings ? "‹ К списку модов" : has ? "▶ Настройки мода" : "Нет настроек", dx + dw / 2, sy2 + 6, has ? 0xFFFFFFFF : 0xFF7880B8);
        pill(g, dx + 6, by, dw - 12, 20, Gfx.in(mx, my, dx + 6, by, dw - 12, 20), true);
        Gfx.ctext(g, "✓ Применить", dx + dw / 2, by + 6, 0xFFFFFFFF);
    }

    // ------------------------------------------------------------ ввод
    @Override
    public boolean mouseClicked(MouseButtonEvent e, boolean dbl) {
        double mx = e.x(), my = e.y();
        if (e.button() != 0) return super.mouseClicked(e, dbl);
        if (Gfx.in(mx, my, search.getX(), search.getY(), search.getWidth(), search.getHeight())) return super.mouseClicked(e, dbl);
        search.setFocused(false);
        if (Gfx.in(mx, my, px + pw - 24, py + 8, 16, 16) || Gfx.in(mx, my, px + pw - 46, py + 8, 16, 16)) {
            PulseSounds.ui("ui_close");
            onClose();
            return true;
        }
        int tx = px + 112;
        for (int i = 0; i < TOPS.length; i++) {
            int w = Gfx.width(TOPS[i]) + 30;
            if (Gfx.in(mx, my, tx, py + 6, w - 4, 20)) { topTab = i; inSettings = false; scrollTarget = 0; PulseSounds.ui("ui_click"); return true; }
            tx += w;
        }
        for (int i = 0; i < CATS.length; i++) {
            if (Gfx.in(mx, my, sx, sy + i * 20, sw, 18)) { cat = i; inSettings = false; scrollTarget = 0; PulseSounds.ui("ui_click"); return true; }
        }
        if (Gfx.in(mx, my, sx, py + ph - 24, sw, 18)) {
            PulseConfig.load();
            build();
            inSettings = false;
            say("Обновлено");
            PulseSounds.ui("ui_click");
            return true;
        }
        if (dw > 0 && selected != null) {
            int by = dy + dh - 24, sy2 = by - 24;
            if (Gfx.in(mx, my, dx + 6, by, dw - 12, 20)) { PulseSounds.ui("ui_click"); onClose(); return true; }
            if (Gfx.in(mx, my, dx + 6, sy2, dw - 12, 20)) {
                if (inSettings) { inSettings = false; scrollTarget = 0; } else openSettings(selected);
                PulseSounds.ui("ui_click");
                return true;
            }
        }
        if (Gfx.in(mx, my, lx, ly, lw, lh)) {
            int cw = lw - 8, y = ly - (int) scroll;
            if (inSettings) {
                if (Gfx.in(mx, my, lx, y, cw, 18)) { inSettings = false; scrollTarget = 0; PulseSounds.ui("ui_back"); return true; }
                y += 21;
            }
            for (Row r : rows()) {
                int h = rowH(r);
                if (Gfx.in(mx, my, lx, y, cw, h)) { rowClick(r, mx, lx, cw, dbl); return true; }
                y += h + 3;
            }
        }
        return super.mouseClicked(e, dbl);
    }

    private void rowClick(Row r, double mx, int x, int w, boolean dbl) {
        switch (r.k) {
            case TOGGLE:
                if (inSettings || mx >= x + w - 40) flip(r);
                else { selected = r; PulseSounds.ui("ui_click"); if (dbl) openSettings(r); }
                break;
            case STEP: {
                int n = r.opts.length, i = r.idx.getAsInt();
                int bw = Math.min(110, w / 2 - 6), bx = x + w - bw - 5;
                i = mx < bx + bw / 2.0 ? (i - 1 + n) % n : (i + 1) % n;
                r.setIdx.accept(i);
                PulseSounds.ui("ui_click");
                break;
            }
            case ACTION:
                PulseSounds.ui("ui_click");
                if (!inSettings) { selected = r; openSettings(r); } else r.act.run();
                break;
            default:
        }
        PulseConfig.save();
    }

    private void flip(Row r) {
        boolean v = !r.get.getAsBoolean();
        r.set.accept(v);
        PulseSounds.ui(v ? "toggle_on" : "toggle_off");
        if (!inSettings) selected = r;
    }

    public boolean mouseScrolled(double mx, double my, double sxx, double syy) {
        if (Gfx.in(mx, my, lx, ly, lw, lh)) { scrollTarget -= syy * 26; return true; }
        return false;
    }

    @Override
    public boolean keyPressed(KeyEvent e) {
        if (e.key() == GLFW.GLFW_KEY_RIGHT_SHIFT && !search.isFocused()) { onClose(); return true; }
        return super.keyPressed(e);
    }

    @Override
    public void onClose() {
        PulseConfig.save();
        if (minecraft != null) minecraft.setScreen(parent);
    }
}
