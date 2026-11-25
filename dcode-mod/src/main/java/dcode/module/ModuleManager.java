package dcode.module;

import java.util.List;

public class ModuleManager {
    private static final List<Module> MODULES = List.of(
            new KillAura(), new Esp(), new AutoTotem(),
            new FpsBoost(), new Sprint(), new FullBright(), new Hud());

    public static List<Module> all() { return MODULES; }

    public static void tick() {
        dcode.Render.lastTick = System.nanoTime();
        net.minecraft.client.MinecraftClient mc = net.minecraft.client.MinecraftClient.getInstance();
        for (Module m : MODULES) {
            if (m.getKey() >= 0 && mc.getWindow() != null) {
                boolean down = net.minecraft.client.util.InputUtil.isKeyPressed(mc.getWindow().getHandle(), m.getKey());
                if (down && !m.keyDown && mc.currentScreen == null) m.toggle();
                m.keyDown = down;
            }
            if (m.isEnabled()) m.onTick();
        }
    }
}
