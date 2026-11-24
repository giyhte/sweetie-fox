package dcode;

import dcode.module.ModuleManager;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import org.lwjgl.glfw.GLFW;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.text.Text;
import java.nio.file.Files;
import java.nio.file.Path;

public class DcodeMod implements ClientModInitializer {
    private static int inboxTick = 0;
    @Override
    public void onInitializeClient() {
        Profile.load();
        Config.load();
        KeyBinding open = KeyBindingHelper.registerKeyBinding(
                new KeyBinding("Открыть меню DCODE", InputUtil.Type.KEYSYM, GLFW.GLFW_KEY_RIGHT_SHIFT, "DCODE"));
        ClientTickEvents.END_CLIENT_TICK.register(mc -> {
            ModuleManager.tick();
            if (++inboxTick >= 20) {
                inboxTick = 0;
                try {
                    Path f = FabricLoader.getInstance().getGameDir().resolve("dcode_inbox.txt");
                    if (mc.player != null && Files.exists(f)) {
                        String t = Files.readString(f);
                        Files.deleteIfExists(f);
                        for (String line : t.split("\\R")) if (!line.isBlank()) mc.player.sendMessage(Text.literal("§d[DCODE] §f" + line), false);
                    }
                } catch (Exception ignored) {}
            }
            while (open.wasPressed()) {
                if (mc.currentScreen == null) mc.setScreen(new DcodeScreen());
            }
        });
    }
}
