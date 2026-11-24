package dcode.module;

import net.minecraft.client.option.CloudRenderMode;
import net.minecraft.client.option.GameOptions;
import net.minecraft.client.option.GraphicsMode;

/** Снижает настройки графики для FPS и возвращает прежние при выключении. */
public class FpsBoost extends Module {
    private int view, sim;
    private GraphicsMode graphics;
    private CloudRenderMode clouds;
    private boolean ao, shadows;

    public FpsBoost() { super("FPS Boost", Category.MISC, "Снижает графику ради FPS"); }

    @Override
    protected void onEnable() {
        GameOptions o = mc.options;
        view = o.getViewDistance().getValue();
        sim = o.getSimulationDistance().getValue();
        graphics = o.getGraphicsMode().getValue();
        clouds = o.getCloudRenderMode().getValue();
        ao = o.getAo().getValue();
        shadows = o.getEntityShadows().getValue();

        o.getViewDistance().setValue(Math.min(view, 6));
        o.getSimulationDistance().setValue(Math.min(sim, 5));
        o.getGraphicsMode().setValue(GraphicsMode.FAST);
        o.getCloudRenderMode().setValue(CloudRenderMode.OFF);
        o.getAo().setValue(false);
        o.getEntityShadows().setValue(false);
    }

    @Override
    protected void onDisable() {
        if (graphics == null) return;
        GameOptions o = mc.options;
        o.getViewDistance().setValue(view);
        o.getSimulationDistance().setValue(sim);
        o.getGraphicsMode().setValue(graphics);
        o.getCloudRenderMode().setValue(clouds);
        o.getAo().setValue(ao);
        o.getEntityShadows().setValue(shadows);
    }
}
