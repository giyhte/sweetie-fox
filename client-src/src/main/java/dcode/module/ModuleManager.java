package dcode.module;

import java.util.List;

public class ModuleManager {
    private static final List<Module> MODULES = List.of(
            new KillAura(), new Esp(), new AutoTotem(),
            new FpsBoost(), new Sprint(), new FullBright(), new Hud());

    public static List<Module> all() { return MODULES; }

    public static void tick() {
        for (Module m : MODULES) if (m.isEnabled()) m.onTick();
    }
}
