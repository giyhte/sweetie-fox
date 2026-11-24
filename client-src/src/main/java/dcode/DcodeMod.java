package dcode;

import dcode.module.ModuleManager;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import org.lwjgl.glfw.GLFW;

public class DcodeMod implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        Profile.load();
        Config.load();
        KeyBinding open = KeyBindingHelper.registerKeyBinding(
                new KeyBinding("Открыть меню DCODE", InputUtil.Type.KEYSYM, GLFW.GLFW_KEY_RIGHT_SHIFT, "DCODE"));
        ClientTickEvents.END_CLIENT_TICK.register(mc -> {
            ModuleManager.tick();
            while (open.wasPressed()) {
                if (mc.currentScreen == null) mc.setScreen(new DcodeScreen());
            }
        });
    }
}
