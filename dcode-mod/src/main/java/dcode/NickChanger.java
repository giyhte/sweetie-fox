package dcode;

import dcode.mixin.MinecraftClientAccessor;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.session.Session;

import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.UUID;

public class NickChanger {
    /** Меняет ник текущей сессии. Новый ник виден серверу при следующем подключении. */
    public static boolean change(String nick) {
        nick = nick == null ? "" : nick.trim();
        if (!nick.matches("[A-Za-z0-9_]{3,16}")) return false;
        MinecraftClient mc = MinecraftClient.getInstance();
        UUID uuid = UUID.nameUUIDFromBytes(("OfflinePlayer:" + nick).getBytes(StandardCharsets.UTF_8));
        Session s = new Session(nick, uuid, "", Optional.empty(), Optional.empty(), Session.AccountType.LEGACY);
        ((MinecraftClientAccessor) mc).dcode$setSession(s);
        try {
            java.nio.file.Files.writeString(net.fabricmc.loader.api.FabricLoader.getInstance().getGameDir().resolve("dcode_nick.txt"), nick);
        } catch (Exception ignored) {}
        return true;
    }
}
