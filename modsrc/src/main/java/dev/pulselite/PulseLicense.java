package dev.pulselite;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import net.fabricmc.loader.api.FabricLoader;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

/**
 * Проверка лицензии прямо в моде: без действующего токена, который кладёт лаунчер перед запуском
 * игры (переменные окружения SF_TOKEN/SF_HWID/SF_LIC_URL), меню не открывается и доп. функции не
 * работают — даже если кто-то скопирует jar и закинет его в другой лаунчер/сборку.
 *
 * Офлайн-запас (как в самом лаунчере) — 3 суток с последней успешной проверки, на случай
 * временных проблем с сетью/сервером.
 */
public final class PulseLicense {
    private PulseLicense() {}

    private static final long OFFLINE_GRACE_MS = 3L * 24 * 3600 * 1000;
    private static final long RECHECK_MS = 60_000;

    private static volatile boolean valid = false;
    private static volatile boolean checked = false;
    private static String token, hwid, url;
    private static Path cacheFile;
    private static long lastOkAt = 0;
    private static Thread worker;

    public static void init() {
        token = System.getenv("SF_TOKEN");
        hwid = System.getenv("SF_HWID");
        url = System.getenv("SF_LIC_URL");
        cacheFile = FabricLoader.getInstance().getConfigDir().resolve("pulselite_lic.cache");
        loadCache();

        if (token == null || token.isEmpty() || url == null || url.isEmpty()) {
            // запущено не через официальный лаунчер Sweetie Fox (нет переменных окружения) — блок
            valid = false;
            checked = true;
            return;
        }
        worker = new Thread(PulseLicense::loop, "pulselite-license");
        worker.setDaemon(true);
        worker.start();
    }

    private static void loop() {
        while (true) {
            checkOnce();
            try { Thread.sleep(RECHECK_MS); } catch (InterruptedException ignored) { return; }
        }
    }

    private static void checkOnce() {
        try {
            JsonObject body = new JsonObject();
            body.addProperty("token", token);
            body.addProperty("hwid", hwid);
            HttpURLConnection c = (HttpURLConnection) URI.create(url + "/api/check").toURL().openConnection();
            c.setRequestMethod("POST");
            c.setConnectTimeout(6000);
            c.setReadTimeout(6000);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            c.setRequestProperty("User-Agent", "SweetieFox-Mod");
            try (OutputStream os = c.getOutputStream()) {
                os.write(new Gson().toJson(body).getBytes(StandardCharsets.UTF_8));
            }
            int code = c.getResponseCode();
            String resp = new String((code >= 400 ? c.getErrorStream() : c.getInputStream()).readAllBytes(),
                    StandardCharsets.UTF_8);
            JsonObject j = new Gson().fromJson(resp, JsonObject.class);
            if (code == 200 && j != null && j.has("ok") && j.get("ok").getAsBoolean()) {
                valid = true;
                lastOkAt = System.currentTimeMillis();
                saveCache();
            } else {
                // сервер явно сказал «нет» (бан/истекла/чужой ПК/другая сессия) — блокируем сразу,
                // офлайн-запас тут не при чём: это не сетевая проблема
                valid = false;
            }
        } catch (Exception net) {
            // сеть недоступна/сервер лёг — даём доиграть, если недавно всё было в порядке
            valid = (lastOkAt > 0) && (System.currentTimeMillis() - lastOkAt < OFFLINE_GRACE_MS);
        } finally {
            checked = true;
        }
    }

    /** true, пока мы ещё ни разу не дождались ответа сервера (чтобы не блокировать на долю секунды при старте). */
    public static boolean pending() {
        return !checked && lastOkAt == 0;
    }

    public static boolean valid() {
        return valid;
    }

    private static void loadCache() {
        try {
            if (Files.exists(cacheFile)) {
                Properties p = new Properties();
                try (var in = Files.newInputStream(cacheFile)) { p.load(in); }
                lastOkAt = Long.parseLong(p.getProperty("last_ok", "0"));
            }
        } catch (Exception ignored) {}
    }

    private static void saveCache() {
        try {
            Properties p = new Properties();
            p.setProperty("last_ok", Long.toString(lastOkAt));
            try (var out = Files.newOutputStream(cacheFile)) { p.store(out, null); }
        } catch (Exception ignored) {}
    }
}
