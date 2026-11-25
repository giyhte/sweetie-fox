package dcode;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.client.MinecraftClient;
import net.minecraft.text.Text;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/** Сам клиент опрашивает сервер: бан/кик/сообщения работают, даже если лаунчер закрыт. */
public class Heartbeat {
    private static boolean started;

    public static void start() {
        if (started || Profile.token.isEmpty() || Profile.url.isEmpty()) return;
        started = true;
        Thread t = new Thread(Heartbeat::loop, "dcode-heartbeat");
        t.setDaemon(true);
        t.start();
    }

    private static void loop() {
        HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(6)).build();
        while (true) {
            try {
                Thread.sleep(5000);
                Profile.load();
                JsonObject b = new JsonObject();
                b.addProperty("token", Profile.token);
                b.addProperty("hwid", Profile.hwid);
                b.addProperty("playing", true);
                b.addProperty("nick", Profile.nick());
                HttpRequest rq = HttpRequest.newBuilder(URI.create(Profile.url + "/api/check")).timeout(Duration.ofSeconds(8))
                        .header("Content-Type", "application/json").header("User-Agent", "DCODE-Mod")
                        .POST(HttpRequest.BodyPublishers.ofString(b.toString(), StandardCharsets.UTF_8)).build();
                HttpResponse<String> r = http.send(rq, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
                JsonObject j = JsonParser.parseString(r.body()).getAsJsonObject();
                MinecraftClient mc = MinecraftClient.getInstance();
                if (j.has("ok") && j.get("ok").getAsBoolean()) {
                    if (j.has("msgs")) for (JsonElement e : j.getAsJsonArray("msgs")) say(mc, e.getAsString());
                    if (j.has("kick")) stop(mc, j.get("kick").getAsString());
                } else {
                    String code = j.has("code") ? j.get("code").getAsString() : "";
                    if (code.equals("banned") || code.equals("expired") || code.equals("hwid"))
                        stop(mc, j.has("error") ? j.get("error").getAsString() : "Доступ закрыт");
                }
            } catch (InterruptedException e) {
                return;
            } catch (Exception ignored) {}
        }
    }

    private static void say(MinecraftClient mc, String m) {
        mc.execute(() -> { if (mc.player != null) mc.player.sendMessage(Text.literal("\u00a7d[DCODE] \u00a7f" + m), false); });
    }

    private static void stop(MinecraftClient mc, String why) throws InterruptedException {
        say(mc, "\u00a7c" + why);
        Thread.sleep(1500);
        mc.execute(mc::scheduleStop);
    }
}
