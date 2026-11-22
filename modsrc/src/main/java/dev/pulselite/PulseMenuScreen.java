package dev.pulselite;

import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.network.chat.Component;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import java.util.function.IntConsumer;
import java.util.function.IntSupplier;
import java.util.function.Supplier;

/**
 * Меню Sweetie Fox. Три вкладки: Основное (HUD, оформление), Визуалы (звуки, ивенты FunTime), Буст FPS.
 * Структура — дерево вкладок: вкладка -> подвкладка -> «чип», в листе — список строк настроек.
 */
public class PulseMenuScreen extends Screen {

    enum K { HEADER, TOGGLE, STEP, SLIDER, BTNS, NOTE, EVENT }

    static final class Row {
        K k;
        String name = "";
        BooleanSupplier get, get2;
        Consumer<Boolean> set, set2;
        String[] opts;
        IntSupplier idx;
        IntConsumer setIdx;
        int min, max, stepV = 1;
        IntSupplier gi;
        IntConsumer si;
        String suf = "";
        Runnable after;
        String[] btn;
        Runnable[] acts;
        float hov, anim = -1, anim2 = -1;
    }

    static final class Node {
        String name, icon = "gear";
        List<Node> kids = new ArrayList<>();
        Supplier<List<Row>> rows;
        Node(String n, String ic) { name = n; icon = ic; }
        Node(String n, String ic, Supplier<List<Row>> r) { name = n; icon = ic; rows = r; }
    }

    // ------------------------------------------------------------ конструкторы строк
    private static Row header(String t) { Row r = new Row(); r.k = K.HEADER; r.name = t; return r; }
    private static Row note(String t) { Row r = new Row(); r.k = K.NOTE; r.name = t; return r; }
    private static Row tog(String n, BooleanSupplier g, Consumer<Boolean> s) {
        Row r = new Row(); r.k = K.TOGGLE; r.name = n; r.get = g; r.set = s; return r;
    }
    private static Row step(String n, String[] o, IntSupplier g, IntConsumer s) {
        Row r = new Row(); r.k = K.STEP; r.name = n; r.opts = o; r.idx = g; r.setIdx = s; return r;
    }
    private static int nearest(int[] vals, int c) {
        int b = 0;
        for (int i = 0; i < vals.length; i++) if (Math.abs(vals[i] - c) < Math.abs(vals[b] - c)) b = i;
        return b;
    }
    private static Row stepInts(String n, int[] vals, IntSupplier cur, IntConsumer set, String suf) {
        String[] o = new String[vals.length];
        for (int i = 0; i < vals.length; i++) o[i] = vals[i] + suf;
        return step(n, o, () -> nearest(vals, cur.getAsInt()), i -> set.accept(vals[i]));
    }
    private static Row slider(String n, int min, int max, int st, String suf, IntSupplier g, IntConsumer s, Runnable after) {
        Row r = new Row(); r.k = K.SLIDER; r.name = n; r.min = min; r.max = max; r.stepV = st; r.suf = suf;
        r.gi = g; r.si = s; r.after = after; return r;
    }
    private static Row btns(String[] names, Runnable... acts) {
        Row r = new Row(); r.k = K.BTNS; r.btn = names; r.acts = acts; return r;
    }
    private static Row btn(String name, Runnable a) { return btns(new String[]{name}, a); }
    private static Row event(String n, String type) {
        Row r = new Row(); r.k = K.EVENT; r.name = n;
        r.get = () -> PulseEvents.shown(type); r.set = v -> PulseEvents.setShown(type, v);
        r.get2 = () -> PulseEvents.soundOn(type); r.set2 = v -> PulseEvents.setSound(type, v);
        return r;
    }

    // ------------------------------------------------------------ состояние
    private final Screen parent;
    private final List<Node> root = new ArrayList<>();
    private final int[] sel = new int[3];
    private List<Row> cache;
    private float scroll, scrollTarget, contentH;
    private String toast = "";
    private long toastUntil;
    private Row lastHover, dragRow;
    private int dragX0, dragW;
    private int px, py, pw, ph, lx, ly, lw, lh, y1, y2;

    private static final String[] CORNERS = {"Лево-верх", "Право-верх", "Лево-низ", "Право-низ"};

    public PulseMenuScreen(Screen parent) {
        super(Component.literal("Sweetie Fox"));
        this.parent = parent;
    }

    private void say(String s) { toast = s; toastUntil = System.currentTimeMillis() + 1800; }
    private int accent() { return 0xFF000000 | (PulseTheme.accent(PulseConfig.get().menuPreset) & 0xFFFFFF); }

    // ------------------------------------------------------------ дерево вкладок
    private void build() {
        root.clear();
        root.add(new Node("Основное", "gear", this::mainRows));

        Node vis = new Node("Визуалы", "visual");
        Node snd = new Node("Звуки", "sound");
        PulseConfig c = PulseConfig.get();
        snd.kids.add(new Node("Попадание", "sound", () -> soundRows("Звук при попадании",
                () -> c.hitSound, v -> c.hitSound = v, () -> c.hitType, v -> c.hitType = v,
                () -> c.hitVolume, v -> c.hitVolume = v, () -> c.hitPitch, v -> c.hitPitch = v)));
        snd.kids.add(new Node("Крит", "sound", () -> soundRows("Звук при крите",
                () -> c.critSound, v -> c.critSound = v, () -> c.critType, v -> c.critType = v,
                () -> c.critVolume, v -> c.critVolume = v, () -> c.critPitch, v -> c.critPitch = v)));
        snd.kids.add(new Node("Убийство", "sound", () -> soundRows("Звук при убийстве",
                () -> c.killSound, v -> c.killSound = v, () -> c.killType, v -> c.killType = v,
                () -> c.killVolume, v -> c.killVolume = v, () -> c.killPitch, v -> c.killPitch = v)));
        vis.kids.add(snd);

        Node ev = new Node("Ивенты FunTime", "event");
        ev.kids.add(new Node("Отображение", "event", this::eventShowRows));
        ev.kids.add(new Node("Фильтр ивентов", "event", this::eventFilterRows));
        ev.kids.add(new Node("Звук ивента", "sound", () -> soundRows("Звук при появлении ивента",
                () -> c.eventSound, v -> c.eventSound = v, () -> c.eventSoundType, v -> c.eventSoundType = v,
                () -> c.eventVolume, v -> c.eventVolume = v, () -> c.eventPitch, v -> c.eventPitch = v)));
        vis.kids.add(ev);
        root.add(vis);

        root.add(new Node("Буст FPS", "perf", this::boostRows));
    }

    // ---- Основное
    private List<Row> mainRows() {
        PulseConfig c = PulseConfig.get();
        List<Row> l = new ArrayList<>();
        l.add(header("Что показывать на экране"));
        l.add(tog("Счётчик FPS", () -> c.hudFps, v -> c.hudFps = v));
        l.add(tog("Пинг", () -> c.hudPing, v -> c.hudPing = v));
        l.add(tog("Координаты (XYZ)", () -> c.hudCoords, v -> c.hudCoords = v));
        l.add(tog("Направление взгляда", () -> c.hudDir, v -> c.hudDir = v));
        l.add(tog("Скорость", () -> c.hudSpeed, v -> c.hudSpeed = v));
        l.add(tog("Память (ОЗУ)", () -> c.hudRam, v -> c.hudRam = v));
        l.add(tog("Часы", () -> c.hudTime, v -> c.hudTime = v));
        l.add(header("Вид HUD"));
        l.add(step("Угол", CORNERS, () -> c.hudCorner, i -> c.hudCorner = i));
        l.add(stepInts("Размер", new int[]{75, 100, 125, 150}, () -> c.hudScale, v -> c.hudScale = v, "%"));
        l.add(tog("Подложка", () -> c.hudBackground, v -> c.hudBackground = v));
        l.add(header("Оформление"));
        l.add(step("Палитра", PulseTheme.NAMES, () -> c.menuPreset, i -> c.menuPreset = i));
        l.add(tog("Градиентное главное меню", () -> c.customTitle, v -> c.customTitle = v));
        l.add(tog("Анимация градиента", () -> c.menuAnimated, v -> c.menuAnimated = v));
        l.add(tog("Лепестки в меню", () -> c.petals, v -> c.petals = v));
        l.add(tog("Звуки интерфейса", () -> c.uiSounds, v -> c.uiSounds = v));
        l.add(slider("Громкость интерфейса", 0, 100, 5, "%", () -> c.uiVolume, v -> c.uiVolume = v, () -> PulseSounds.ui("ui_click")));
        l.add(header("Прочее"));
        l.add(note("Right Shift — открыть/закрыть меню. Клавиша меняется в Управлении."));
        l.add(note("Конфиг: config/pulselite.json"));
        l.add(btn("Сбросить все настройки", () -> { PulseConfig.reset(); cache = null; say("Настройки сброшены"); }));
        return l;
    }

    // ---- Звуки
    private List<Row> soundRows(String title, BooleanSupplier on, Consumer<Boolean> setOn,
                                IntSupplier type, IntConsumer setType, IntSupplier vol, IntConsumer setVol,
                                IntSupplier pitch, IntConsumer setPitch) {
        Runnable test = () -> PulseSounds.playLib(type.getAsInt(), vol.getAsInt(), pitch.getAsInt());
        List<Row> l = new ArrayList<>();
        l.add(header(title));
        l.add(tog("Включено", on, setOn));
        l.add(step("Звук", PulseSounds.LIB_NAMES, () -> Math.floorMod(type.getAsInt(), PulseSounds.LIB_NAMES.length),
                i -> { setType.accept(i); test.run(); }));
        l.add(slider("Громкость", 0, 100, 5, "%", vol, setVol, test));
        l.add(step("Тон", PulseSounds.PITCH_NAMES, () -> Math.floorMod(pitch.getAsInt(), PulseSounds.PITCH_NAMES.length),
                i -> { setPitch.accept(i); test.run(); }));
        l.add(btn("▶ Проиграть тест", test));
        l.add(note("Звук, громкость и тон можно менять отдельно для каждого события."));
        return l;
    }

    // ---- Ивенты
    private List<Row> eventShowRows() {
        PulseConfig c = PulseConfig.get();
        List<Row> l = new ArrayList<>();
        l.add(header("Трекер ивентов"));
        l.add(tog("Трекер включён", () -> c.eventTracker, v -> c.eventTracker = v));
        l.add(tog("Список на экране", () -> c.eventList, v -> c.eventList = v));
        l.add(step("Угол списка", CORNERS, () -> c.eventCorner, i -> c.eventCorner = i));
        l.add(step("Стиль списка", new String[]{"Карточки", "Компакт"}, () -> c.eventStyle, i -> c.eventStyle = i));
        l.add(stepInts("Макс. в списке", new int[]{1, 2, 3, 4, 5, 6}, () -> c.eventMax, v -> c.eventMax = v, ""));
        l.add(tog("Показывать координаты", () -> c.eventCoords, v -> c.eventCoords = v));
        l.add(header("Метка в мире"));
        l.add(tog("Метка включена", () -> c.eventMarker, v -> c.eventMarker = v));
        l.add(step("Стиль метки", new String[]{"Ромб + название", "Только дистанция"}, () -> c.eventMarkerStyle, i -> c.eventMarkerStyle = i));
        l.add(step("Метка живёт", new String[]{"2 мин", "5 мин", "10 мин", "20 мин"},
                () -> c.eventTimeout <= 120 ? 0 : c.eventTimeout <= 300 ? 1 : c.eventTimeout <= 600 ? 2 : 3,
                i -> c.eventTimeout = new int[]{120, 300, 600, 1200}[i]));
        l.add(btns(new String[]{"Тестовая метка", "Очистить метки"},
                () -> {
                    if (minecraft != null && minecraft.player != null) { PulseEvents.test(); say("Метка создана"); }
                    else say("Зайди в мир");
                },
                () -> { PulseEvents.LIST.clear(); say("Метки очищены"); }));
        l.add(note("Ловит чат: слово-ключ + координаты."));
        return l;
    }

    private List<Row> eventFilterRows() {
        List<Row> l = new ArrayList<>();
        l.add(header("Какие ивенты показывать"));
        l.add(note("Показ — список и метка в мире. Звук — сигнал при появлении."));
        for (String[] t : PulseEvents.TYPES) l.add(event(t[1], t[0]));
        l.add(btns(new String[]{"Включить все", "Выключить все"},
                () -> { for (String[] t : PulseEvents.TYPES) { PulseEvents.setShown(t[0], true); PulseEvents.setSound(t[0], true); } say("Все ивенты включены"); },
                () -> { for (String[] t : PulseEvents.TYPES) PulseEvents.setShown(t[0], false); say("Все ивенты скрыты"); }));
        l.add(note("Свои слова: config/pulselite.json -> eventKeywords (тип «Другое»)."));
        return l;
    }

    // ---- Буст FPS
    private static Row bstep(String name, String key, int[] vals, String suf) {
        return stepInts(name, vals, () -> PulseBoost.get(key), v -> PulseBoost.request(key, v), suf);
    }
    private static Row btog(String name, String key) {
        return tog(name, () -> PulseBoost.get(key) != 0, v -> PulseBoost.request(key, v ? 1 : 0));
    }
    private static Row bopts(String name, String key, String[] opts) {
        return step(name, opts, () -> PulseBoost.get(key), i -> PulseBoost.request(key, i));
    }

    private List<Row> boostRows() {
        List<Row> l = new ArrayList<>();
        l.add(header("Пресеты"));
        String[] pn = {"Макс. FPS", "Баланс", "Красиво", "Как в ваниле"};
        l.add(btns(pn,
                () -> { PulseBoost.preset(0); say("Макс. FPS — применяю по шагам"); },
                () -> { PulseBoost.preset(1); say("Баланс — применяю по шагам"); },
                () -> { PulseBoost.preset(2); say("Красиво — применяю по шагам"); },
                () -> { PulseBoost.preset(3); say("Ваниль — применяю по шагам"); }));
        l.add(btn("Откатить к тому, что было при открытии меню", () -> { PulseBoost.revert(); say("Откатываю"); }));
        l.add(header("Дальность"));
        int cap = PulseBoost.maxRd();
        int[] rd = {2, 3, 4, 6, 8, 10, 12, 16, 24, 32};
        int n = 0;
        for (int v : rd) if (v <= cap) n++;
        int[] rdv = new int[n];
        n = 0;
        for (int v : rd) if (v <= cap) rdv[n++] = v;
        l.add(bstep("Прорисовка", PulseBoost.RD, rdv, " чанк."));
        l.add(bstep("Симуляция", PulseBoost.SIM, new int[]{5, 6, 8, 10, 12, 16}, " чанк."));
        l.add(bstep("Лимит FPS", PulseBoost.FPS, new int[]{30, 60, 90, 120, 160, 200, 240, 260}, ""));
        l.add(btog("VSync", PulseBoost.VSYNC));
        l.add(header("Графика"));
        l.add(bopts("Частицы", PulseBoost.PART, new String[]{"Все", "Меньше", "Минимум"}));
        l.add(bopts("Облака", PulseBoost.CLOUD, new String[]{"Выкл", "Быстро", "Красиво"}));
        l.add(btog("Тени сущностей", PulseBoost.SHAD));
        l.add(btog("Покачивание камеры", PulseBoost.BOB));
        l.add(bstep("Дальность сущностей", PulseBoost.ENT, new int[]{50, 75, 100, 150, 200}, "%"));
        l.add(bstep("Сглаж. биомов", PulseBoost.BIOME, new int[]{0, 1, 2, 3, 5, 7}, ""));
        l.add(bstep("Mipmap", PulseBoost.MIP, new int[]{0, 1, 2, 3, 4}, ""));
        l.add(note("Настройки применяются по одной, тяжёлые (прорисовка, биомы, mipmap) — с паузой."));
        l.add(note("Так нет фризов и вылетов. Прорисовка ограничена " + cap + " чанк. по доступной ОЗУ."));
        return l;
    }

    // ------------------------------------------------------------ навигация
    private List<Node> lvl1() { return root.get(sel[0]).kids; }
    private List<Node> lvl2() { List<Node> a = lvl1(); return a.isEmpty() ? a : a.get(sel[1]).kids; }
    private Node leaf() {
        Node n = root.get(sel[0]);
        if (!n.kids.isEmpty()) { n = n.kids.get(sel[1]); if (!n.kids.isEmpty()) n = n.kids.get(sel[2]); }
        return n;
    }
    private List<Row> rows() {
        if (cache == null) cache = leaf().rows.get();
        return cache;
    }
    private void go(int lvl, int i) {
        sel[lvl] = i;
        for (int j = lvl + 1; j < 3; j++) sel[j] = 0;
        cache = null; scroll = 0; scrollTarget = 0; dragRow = null;
        PulseSounds.ui("ui_click");
    }

    private int tabW(int lvl, Node n) { return Gfx.width(n.name) + (lvl == 2 ? 16 : 30) + 4; }
    private List<Node> level(int lvl) { return lvl == 0 ? root : lvl == 1 ? lvl1() : lvl2(); }
    private int[] tabRect(int lvl, int i) {
        List<Node> ns = level(lvl);
        int x = lvl == 0 ? px + 128 : px + 8;
        for (int j = 0; j < i; j++) x += tabW(lvl, ns.get(j));
        int y = lvl == 0 ? py + 6 : lvl == 1 ? y1 : y2;
        int h = lvl == 0 ? 20 : lvl == 1 ? 18 : 16;
        return new int[]{x, y, tabW(lvl, ns.get(i)) - 4, h};
    }

    private void layout() {
        pw = Math.min(520, width - 8);
        ph = Math.min(320, height - 8);
        px = (width - pw) / 2;
        py = (height - ph) / 2;
        int y = py + 32;
        y1 = y;
        if (!lvl1().isEmpty()) y += 22;
        y2 = y;
        if (!lvl2().isEmpty()) y += 20;
        lx = px + 8;
        lw = pw - 16;
        ly = y + 2;
        lh = py + ph - 16 - ly;
    }

    @Override
    protected void init() {
        if (root.isEmpty()) { build(); PulseBoost.snapshot(); }
    }

    private int rowH(Row r) { return r.k == K.NOTE ? 13 : r.k == K.HEADER ? 18 : 22; }
    private int gap(Row r) { return r.k == K.NOTE ? 0 : 3; }

    // ------------------------------------------------------------ отрисовка
    private void scaled(GuiGraphics g, String s, int x, int y, float sc, int col) {
        g.pose().pushMatrix();
        g.pose().translate((float) x, (float) y);
        g.pose().scale(sc, sc);
        Gfx.text(g, s, 0, 0, col);
        g.pose().popMatrix();
    }

    private void pill(GuiGraphics g, int x, int y, int w, int h, boolean hot, boolean strong) {
        int a = accent() & 0xFFFFFF;
        Gfx.rr(g, x, y, w, h, hot ? Gfx.argb(0xFF, a) : strong ? 0xFF3A3F9E : 0xFF1B1F52);
        Gfx.border(g, x, y, w, h, hot ? 0xFFFFFFFF : Gfx.argb(0xAA, a));
    }

    private float tg(GuiGraphics g, int x, int y, boolean on, float anim) {
        if (anim < 0) anim = on ? 1f : 0f;
        anim = Gfx.approach(anim, on ? 1f : 0f, 0.3f);
        int a = accent() & 0xFFFFFF;
        Gfx.rr(g, x, y, 28, 13, on ? Gfx.argb(0xFF, a) : 0xFF22254F);
        Gfx.border(g, x, y, 28, 13, 0xCCFFFFFF);
        Gfx.rr(g, x + 2 + (int) (anim * 15), y + 2, 9, 9, 0xFFFFFFFF);
        return anim;
    }

    private void spark(GuiGraphics g, int x, int y, long now, int phase) {
        float a = 0.5f + 0.5f * (float) Math.sin(now / 500.0 + phase);
        int s = 6 + (int) (a * 4);
        g.blit(RenderPipelines.GUI_TEXTURED, Gfx.id("textures/gui/sparkle.png"), x, y, 0f, 0f, s, s, 32, 32, 32, 32);
    }

    @Override
    public void render(GuiGraphics g, int mx, int my, float pt) {
        if (root.isEmpty()) return;
        layout();
        PulseConfig c = PulseConfig.get();
        long now = System.currentTimeMillis();
        int acc = accent(), accRgb = acc & 0xFFFFFF;
        if (minecraft != null && minecraft.level != null) {
            g.fill(0, 0, width, height, 0x88000010);
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
        int cxb = px + pw - 24;
        pill(g, cxb, py + 8, 16, 16, Gfx.in(mx, my, cxb, py + 8, 16, 16), false);
        Gfx.ctext(g, "x", cxb + 8, py + 12, 0xFFFFFFFF);
        spark(g, px + pw - 44, py + 10, now, 0);
        spark(g, px + pw - 16, py + ph - 24, now, 2);

        // --- вкладки трёх уровней
        for (int lvl = 0; lvl < 3; lvl++) {
            List<Node> ns = level(lvl);
            for (int i = 0; i < ns.size(); i++) {
                int[] r = tabRect(lvl, i);
                boolean s = sel[lvl] == i, h = Gfx.in(mx, my, r[0], r[1], r[2], r[3]);
                pill(g, r[0], r[1], r[2], r[3], s, false);
                if (h && !s) Gfx.border(g, r[0], r[1], r[2], r[3], 0xFFFFFFFF);
                if (lvl < 2) {
                    Gfx.icon(g, ns.get(i).icon, r[0] + 5, r[1] + (r[3] - 10) / 2, 10);
                    Gfx.text(g, ns.get(i).name, r[0] + 19, r[1] + (r[3] - 8) / 2 + 1, 0xFFFFFFFF);
                } else {
                    Gfx.ctext(g, ns.get(i).name, r[0] + r[2] / 2, r[1] + (r[3] - 8) / 2 + 1, 0xFFFFFFFF);
                }
            }
        }

        // --- список настроек
        List<Row> rs = rows();
        scroll = Gfx.approach(scroll, scrollTarget, 0.3f);
        Row hover = null;
        int cw = lw - 8;
        int y = ly - (int) scroll;
        g.enableScissor(lx, ly, lx + lw, ly + lh);
        try {
            for (Row r : rs) {
                int h = rowH(r);
                if (y + h > ly && y < ly + lh) {
                    boolean in = Gfx.in(mx, my, lx, ly, lw, lh) && Gfx.in(mx, my, lx, y, cw, h);
                    if (in && r.k != K.NOTE && r.k != K.HEADER) hover = r;
                    drawRow(g, r, lx, y, cw, h, in, mx, my, accRgb);
                }
                y += h + gap(r);
            }
        } finally {
            g.disableScissor();
        }
        contentH = y - (ly - scroll);
        float maxS = Math.max(0, contentH - lh);
        scrollTarget = Math.max(0, Math.min(maxS, scrollTarget));
        if (maxS > 0) {
            int bh = Math.max(16, (int) (lh * lh / contentH));
            int by = ly + (int) ((lh - bh) * (scroll / maxS));
            g.fill(lx + lw - 3, ly, lx + lw - 1, ly + lh, 0x33FFFFFF);
            g.fill(lx + lw - 3, by, lx + lw - 1, by + bh, acc);
        }
        if (hover != lastHover) {
            if (hover != null) PulseSounds.ui("ui_hover");
            lastHover = hover;
        }

        // --- нижняя строка
        int fy = py + ph - 13;
        Gfx.text(g, "Right Shift — закрыть", px + 10, fy, 0xFF6F7AC0);
        int pend = PulseBoost.pendingCount();
        if (pend > 0) {
            String t = "Применяю настройки… осталось " + pend;
            Gfx.text(g, t, px + pw - 10 - Gfx.width(t), fy, 0xFFFFD36B);
        }
        if (now < toastUntil) {
            int w = Gfx.width(toast) + 16, tx2 = lx + (lw - w) / 2;
            Gfx.rr(g, tx2, ly + lh - 20, w, 16, 0xEE1B1F52);
            Gfx.border(g, tx2, ly + lh - 20, w, 16, acc);
            Gfx.ctext(g, toast, lx + lw / 2, ly + lh - 16, 0xFFFFFFFF);
        }
    }

    private void drawRow(GuiGraphics g, Row r, int x, int y, int w, int h, boolean in, int mx, int my, int accRgb) {
        if (r.k == K.NOTE) { Gfx.text(g, r.name, x + 4, y + 2, 0xFF8F9AE0); return; }
        if (r.k == K.HEADER) {
            Gfx.text(g, r.name, x + 4, y + 5, 0xFF000000 | accRgb | 0x303030);
            g.fill(x + 4 + Gfx.width(r.name) + 6, y + 9, x + w, y + 10, Gfx.argb(0x66, accRgb));
            return;
        }
        r.hov = Gfx.approach(r.hov, in ? 1f : 0f, 0.25f);
        if (r.k != K.BTNS) {
            Gfx.rr(g, x, y, w, h, Gfx.argb(0xB0 + (int) (r.hov * 0x30), 0x10143C));
            Gfx.border(g, x, y, w, h, Gfx.argb(0x66 + (int) (r.hov * 0x99), accRgb));
        }
        int ty = y + (h - 8) / 2;
        switch (r.k) {
            case TOGGLE:
                Gfx.text(g, r.name, x + 8, ty, 0xFFFFFFFF);
                r.anim = tg(g, x + w - 34, y + (h - 13) / 2, r.get.getAsBoolean(), r.anim);
                break;
            case EVENT:
                Gfx.text(g, r.name, x + 8, ty, 0xFFFFFFFF);
                r.anim = tg(g, x + w - 76, y + (h - 13) / 2, r.get.getAsBoolean(), r.anim);
                r.anim2 = tg(g, x + w - 34, y + (h - 13) / 2, r.get2.getAsBoolean(), r.anim2);
                break;
            case STEP: {
                Gfx.text(g, r.name, x + 8, ty, 0xFFFFFFFF);
                int bw = stepW(w), bx = x + w - bw - 5;
                String v = r.opts[Math.max(0, Math.min(r.opts.length - 1, r.idx.getAsInt()))];
                Gfx.rr(g, bx, y + 3, bw, h - 6, 0xFF1B2060);
                Gfx.text(g, "‹", bx + 5, ty, 0xFF000000 | accRgb);
                Gfx.text(g, "›", bx + bw - 10, ty, 0xFF000000 | accRgb);
                Gfx.ctext(g, v, bx + bw / 2, ty, 0xFFFFFFFF);
                break;
            }
            case SLIDER: {
                Gfx.text(g, r.name, x + 8, ty, 0xFFFFFFFF);
                int tx = sliderX(x, w), tw = sliderW();
                int val = Math.max(r.min, Math.min(r.max, r.gi.getAsInt()));
                float t = r.max == r.min ? 0f : (val - r.min) / (float) (r.max - r.min);
                g.fill(tx, y + h / 2 - 1, tx + tw, y + h / 2 + 1, 0xFF2A2F78);
                g.fill(tx, y + h / 2 - 1, tx + (int) (tw * t), y + h / 2 + 1, 0xFF000000 | accRgb);
                Gfx.rr(g, tx + (int) (tw * t) - 3, y + h / 2 - 6, 7, 12, 0xFFFFFFFF);
                String vs = val + r.suf;
                Gfx.text(g, vs, x + w - 8 - Gfx.width(vs), ty, 0xFFB9C2FF);
                break;
            }
            case BTNS: {
                int n = r.btn.length, gp = 4, bw = (w - gp * (n - 1)) / n;
                for (int i = 0; i < n; i++) {
                    int bx = x + i * (bw + gp);
                    boolean hot = Gfx.in(mx, my, bx, y, bw, h);
                    pill(g, bx, y, bw, h, hot, false);
                    Gfx.ctext(g, r.btn[i], bx + bw / 2, ty, 0xFFFFFFFF);
                }
                break;
            }
            default:
        }
    }

    private int stepW(int w) { return Math.min(150, w / 2 - 6); }
    private int sliderW() { return 110; }
    private int sliderX(int x, int w) { return x + w - 8 - 40 - sliderW() - 8; }

    private void setSlider(Row r, double mx, int tx, int tw) {
        double t = Math.max(0, Math.min(1, (mx - tx) / (double) tw));
        int v = r.min + (int) Math.round(t * (r.max - r.min) / r.stepV) * r.stepV;
        r.si.accept(Math.max(r.min, Math.min(r.max, v)));
    }

    // ------------------------------------------------------------ ввод
    @Override
    public boolean mouseClicked(MouseButtonEvent e, boolean dbl) {
        double mx = e.x(), my = e.y();
        if (e.button() != 0 || root.isEmpty()) return super.mouseClicked(e, dbl);
        layout();
        if (Gfx.in(mx, my, px + pw - 24, py + 8, 16, 16)) {
            PulseSounds.ui("ui_close");
            onClose();
            return true;
        }
        for (int lvl = 0; lvl < 3; lvl++) {
            List<Node> ns = level(lvl);
            for (int i = 0; i < ns.size(); i++) {
                int[] r = tabRect(lvl, i);
                if (Gfx.in(mx, my, r[0], r[1], r[2], r[3])) { if (sel[lvl] != i) go(lvl, i); return true; }
            }
        }
        if (Gfx.in(mx, my, lx, ly, lw, lh)) {
            int cw = lw - 8, y = ly - (int) scroll;
            for (Row r : rows()) {
                int h = rowH(r);
                if (Gfx.in(mx, my, lx, y, cw, h)) { rowClick(r, mx, lx, y, cw); return true; }
                y += h + gap(r);
            }
        }
        return super.mouseClicked(e, dbl);
    }

    private void rowClick(Row r, double mx, int x, int y, int w) {
        switch (r.k) {
            case TOGGLE: {
                boolean v = !r.get.getAsBoolean();
                r.set.accept(v);
                PulseSounds.ui(v ? "toggle_on" : "toggle_off");
                break;
            }
            case EVENT: {
                if (mx >= x + w - 40) { boolean v = !r.get2.getAsBoolean(); r.set2.accept(v); PulseSounds.ui(v ? "toggle_on" : "toggle_off"); }
                else if (mx >= x + w - 82) { boolean v = !r.get.getAsBoolean(); r.set.accept(v); PulseSounds.ui(v ? "toggle_on" : "toggle_off"); }
                break;
            }
            case STEP: {
                int n = r.opts.length, i = Math.max(0, Math.min(n - 1, r.idx.getAsInt()));
                int bw = stepW(w), bx = x + w - bw - 5;
                if (mx < bx - 4) return;
                i = mx < bx + bw / 2.0 ? (i - 1 + n) % n : (i + 1) % n;
                r.setIdx.accept(i);
                PulseSounds.ui("ui_click");
                break;
            }
            case SLIDER: {
                int tx = sliderX(x, w), tw = sliderW();
                if (mx >= tx - 6 && mx <= tx + tw + 6) {
                    dragRow = r; dragX0 = tx; dragW = tw;
                    setSlider(r, mx, tx, tw);
                }
                break;
            }
            case BTNS: {
                int n = r.btn.length, gp = 4, bw = (w - gp * (n - 1)) / n;
                for (int i = 0; i < n; i++) {
                    int bx = x + i * (bw + gp);
                    if (mx >= bx && mx < bx + bw) {
                        PulseSounds.ui("ui_click");
                        try { r.acts[i].run(); } catch (Throwable t) { System.err.println("[PulseLite] action failed: " + t); }
                        break;
                    }
                }
                break;
            }
            default: return;
        }
        PulseConfig.save();
    }

    public boolean mouseDragged(MouseButtonEvent e, double dx, double dy) {
        if (dragRow != null && e.button() == 0) { setSlider(dragRow, e.x(), dragX0, dragW); return true; }
        return false;
    }

    public boolean mouseReleased(MouseButtonEvent e) {
        if (dragRow != null) {
            Row r = dragRow;
            dragRow = null;
            PulseConfig.save();
            if (r.after != null) r.after.run();
            return true;
        }
        return false;
    }

    public boolean mouseScrolled(double mx, double my, double sxx, double syy) {
        if (Gfx.in(mx, my, lx, ly, lw, lh)) { scrollTarget -= syy * 26; return true; }
        return false;
    }

    @Override
    public boolean keyPressed(KeyEvent e) {
        if (e.key() == GLFW.GLFW_KEY_RIGHT_SHIFT) { onClose(); return true; }
        return super.keyPressed(e);
    }

    @Override
    public void onClose() {
        PulseConfig.save();
        if (minecraft != null) minecraft.setScreen(parent);
    }
}
