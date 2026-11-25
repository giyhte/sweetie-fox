package dcode;

import com.mojang.blaze3d.systems.RenderSystem;
import dcode.module.KillAura;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.minecraft.client.gl.ShaderProgramKeys;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.util.math.Vec3d;
import org.joml.Matrix4f;
import org.joml.Vector4f;

/** Общие данные рендера: матрицы камеры (для 2D-проекции в ESP), partial tick, подготовка GL для эффектов. */
public final class Render {
    private Render() {}

    public static final Matrix4f VIEW = new Matrix4f();
    public static final Matrix4f PROJ = new Matrix4f();
    public static volatile Vec3d cam = Vec3d.ZERO;
    public static volatile boolean ready;
    /** partial tick именно этого кадра мира — по нему же считается матрица камеры, иначе рамка ESP дрожит. */
    public static volatile float frameDelta = -1f;
    public static volatile long lastTick = System.nanoTime();

    public static void init() {
        WorldRenderEvents.LAST.register(ctx -> {
            MatrixStack ms = ctx.matrixStack();
            if (ms == null) return;
            VIEW.set(ms.peek().getPositionMatrix());
            PROJ.set(ctx.projectionMatrix());
            cam = ctx.camera().getPos();
            try { frameDelta = ctx.tickCounter().getTickDelta(true); } catch (Throwable t) { frameDelta = -1f; }
            ready = true;
            try { KillAura.renderFx(VIEW, cam); } catch (Throwable ignored) {}
        });
    }

    /** Доля тика между двумя клиентскими тиками (0..1), считаем сами по времени. */
    public static float partial() {
        if (frameDelta >= 0f) return Math.min(frameDelta, 1f);
        float p = (System.nanoTime() - lastTick) / 50_000_000f;
        return p < 0f ? 0f : Math.min(p, 1f);
    }

    /** Мир -> экран (масштабированные GUI-координаты). null, если точка за камерой. */
    public static float[] project(double x, double y, double z, int sw, int sh) {
        Vec3d c = cam;
        Vector4f v = new Vector4f((float) (x - c.x), (float) (y - c.y), (float) (z - c.z), 1f);
        v.mul(VIEW);
        v.mul(PROJ);
        if (v.w <= 0.05f) return null;
        float nx = v.x / v.w, ny = v.y / v.w;
        return new float[]{(nx * 0.5f + 0.5f) * sw, (0.5f - ny * 0.5f) * sh};
    }

    public static int hue(float h, int alpha) {
        h = h - (float) Math.floor(h);
        return (Math.max(0, Math.min(255, alpha)) << 24) | (java.awt.Color.HSBtoRGB(h, 0.62f, 1f) & 0xFFFFFF);
    }

    public static void beginFx() {
        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.disableDepthTest();
        RenderSystem.disableCull();
        RenderSystem.depthMask(false);
        RenderSystem.setShader(ShaderProgramKeys.POSITION_COLOR);
    }

    public static void endFx() {
        RenderSystem.depthMask(true);
        RenderSystem.enableCull();
        RenderSystem.enableDepthTest();
        RenderSystem.disableBlend();
    }
}
