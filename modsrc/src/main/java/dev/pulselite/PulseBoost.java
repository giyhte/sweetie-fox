package dev.pulselite;

import net.minecraft.client.CloudStatus;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Options;
import net.minecraft.server.level.ParticleStatus;

import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Буст FPS. Раньше пресет менял ~12 настроек в одном кадре: смена mipmap перезагружает атласы текстур,
 * смена сглаживания биомов и прорисовки пересобирает все чанки — отсюда фризы на секунды и вылеты.
 * Теперь изменения встают в очередь и применяются по одному: лёгкие сразу, тяжёлые (прорисовка,
 * биомы, mipmap) — с задержкой после последнего клика и не чаще раза в 1.5 с, только если значение реально изменилось.
 */
public final class PulseBoost {
    private PulseBoost() {}

    public static final String RD = "rd", SIM = "sim", FPS = "fps", VSYNC = "vsync", PART = "part", CLOUD = "cloud",
            SHAD = "shad", MIP = "mip", BIOME = "biome", BOB = "bob", ENT = "ent";
    public static final String[] ALL = {SIM, FPS, VSYNC, PART, CLOUD, SHAD, BOB, ENT, RD, BIOME, MIP};

    private static final Map<String, Integer> PENDING = new LinkedHashMap<>();
    private static final Map<String, Long> STAMP = new HashMap<>();
    private static final Map<String, Integer> SNAP = new HashMap<>();
    private static long lastHeavy;
    private static boolean dirty;

    private static boolean heavy(String k) { return k.equals(RD) || k.equals(BIOME) || k.equals(MIP); }

    /** Потолок прорисовки по доступной памяти — защита от нехватки ОЗУ. */
    public static int maxRd() {
        long mb = Runtime.getRuntime().maxMemory() >> 20;
        return mb >= 3500 ? 32 : mb >= 2500 ? 24 : 16;
    }

    public static int pendingCount() { return PENDING.size(); }

    // ------------------------------------------------------------ чтение / запись настроек игры
    private static int read(String k) {
        Options o = Minecraft.getInstance().options;
        switch (k) {
            case RD: return o.renderDistance().get();
            case SIM: return o.simulationDistance().get();
            case FPS: return o.framerateLimit().get();
            case VSYNC: return o.enableVsync().get() ? 1 : 0;
            case PART: {
                ParticleStatus p = o.particles().get();
                return p == ParticleStatus.ALL ? 0 : p == ParticleStatus.DECREASED ? 1 : 2;
            }
            case CLOUD: {
                CloudStatus s = o.cloudStatus().get();
                return s == CloudStatus.OFF ? 0 : s == CloudStatus.FAST ? 1 : 2;
            }
            case SHAD: return o.entityShadows().get() ? 1 : 0;
            case MIP: return o.mipmapLevels().get();
            case BIOME: return o.biomeBlendRadius().get();
            case BOB: return o.bobView().get() ? 1 : 0;
            case ENT: return (int) Math.round(o.entityDistanceScaling().get() * 100.0);
            default: return 0;
        }
    }

    private static void write(String k, int v) {
        Options o = Minecraft.getInstance().options;
        switch (k) {
            case RD: o.renderDistance().set(Math.max(2, Math.min(maxRd(), v))); break;
            case SIM: o.simulationDistance().set(Math.max(5, Math.min(32, v))); break;
            case FPS: o.framerateLimit().set(Math.max(10, Math.min(260, v))); break;
            case VSYNC: o.enableVsync().set(v != 0); break;
            case PART: o.particles().set(v == 0 ? ParticleStatus.ALL : v == 1 ? ParticleStatus.DECREASED : ParticleStatus.MINIMAL); break;
            case CLOUD: o.cloudStatus().set(v == 0 ? CloudStatus.OFF : v == 1 ? CloudStatus.FAST : CloudStatus.FANCY); break;
            case SHAD: o.entityShadows().set(v != 0); break;
            case MIP: o.mipmapLevels().set(Math.max(0, Math.min(4, v))); break;
            case BIOME: o.biomeBlendRadius().set(Math.max(0, Math.min(7, v))); break;
            case BOB: o.bobView().set(v != 0); break;
            case ENT: o.entityDistanceScaling().set(Math.max(50, Math.min(500, v)) / 100.0); break;
            default:
        }
    }

    /** Значение для интерфейса: ожидающее (если есть) или текущее. */
    public static int get(String k) {
        Integer p = PENDING.get(k);
        if (p != null) return p;
        try { return read(k); } catch (Throwable t) { return 0; }
    }

    /** Поставить изменение в очередь (применится в tick). */
    public static void request(String k, int v) {
        try {
            if (PENDING.isEmpty() && read(k) == v) return;
        } catch (Throwable t) { return; }
        PENDING.put(k, v);
        STAMP.put(k, System.currentTimeMillis());
    }

    public static void snapshot() {
        SNAP.clear();
        for (String k : ALL) { try { SNAP.put(k, read(k)); } catch (Throwable t) { /* ignore */ } }
    }

    public static void revert() {
        for (String k : ALL) { Integer v = SNAP.get(k); if (v != null) request(k, v); }
    }

    /** Пресеты: 0 Макс.FPS, 1 Баланс, 2 Красиво, 3 Ваниль. mipmap в пресеты НЕ входит (тяжёлая перезагрузка текстур). */
    public static void preset(int n) {
        int[][] iv = {{6, 5, 240, 0}, {10, 8, 160, 1}, {16, 12, 120, 3}, {12, 12, 120, 2}};
        int[] v = iv[Math.max(0, Math.min(3, n))];
        request(FPS, v[2]);
        request(VSYNC, n >= 2 ? 1 : 0);
        request(SHAD, n >= 2 ? 1 : 0);
        request(BOB, n >= 2 ? 1 : 0);
        request(ENT, n == 0 ? 75 : n == 1 ? 100 : 150);
        request(PART, n == 0 ? 2 : n == 1 ? 1 : 0);
        request(CLOUD, n == 0 ? 0 : n == 1 ? 1 : 2);
        request(SIM, v[1]);
        request(RD, Math.min(v[0], maxRd()));
        request(BIOME, v[3]);
    }

    // ------------------------------------------------------------ применение (каждый клиентский тик)
    public static void tick(Minecraft mc) {
        if (PENDING.isEmpty()) {
            if (dirty) { dirty = false; try { mc.options.save(); } catch (Throwable t) { /* ignore */ } }
            return;
        }
        long now = System.currentTimeMillis();
        boolean inWorld = mc.level != null;
        int applied = 0;
        Iterator<Map.Entry<String, Integer>> it = PENDING.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<String, Integer> e = it.next();
            String k = e.getKey();
            boolean hv = heavy(k) && inWorld;
            if (hv) {
                if (now - STAMP.getOrDefault(k, 0L) < 600) continue;   // ждём, пока игрок перестанет кликать
                if (now - lastHeavy < 1500) continue;                  // не больше одной тяжёлой операции за раз
            }
            try {
                if (read(k) != e.getValue()) write(k, e.getValue());
            } catch (Throwable t) {
                System.err.println("[PulseLite] boost " + k + " failed: " + t);
            }
            it.remove();
            dirty = true;
            if (hv) { lastHeavy = now; break; }
            if (++applied >= 4) break;
        }
    }
}
