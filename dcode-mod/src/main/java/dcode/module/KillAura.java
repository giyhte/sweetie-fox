package dcode.module;

import dcode.Render;
import dcode.setting.BoolSetting;
import dcode.setting.ModeSetting;
import dcode.setting.NumSetting;
import net.minecraft.client.render.BufferBuilder;
import net.minecraft.client.render.BufferRenderer;
import net.minecraft.client.render.Tessellator;
import net.minecraft.client.render.VertexFormat;
import net.minecraft.client.render.VertexFormats;
import net.minecraft.entity.Entity;
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.decoration.ArmorStandEntity;
import net.minecraft.entity.effect.StatusEffects;
import net.minecraft.entity.mob.Monster;
import net.minecraft.entity.passive.PassiveEntity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.Hand;
import net.minecraft.util.math.Box;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.Vec3d;
import org.joml.Matrix4f;

import java.util.Random;

public class KillAura extends Module {
    private final NumSetting range = add(new NumSetting("Дистанция атаки", 3.0, 2.0, 6.0, 0.1));
    private final NumSetting scan = add(new NumSetting("Радиус захвата", 4.0, 2.0, 8.0, 0.1));
    private final ModeSetting priority = add(new ModeSetting("Приоритет", 0, "Дистанция", "Здоровье", "Угол", "Броня"));
    private final BoolSetting players = add(new BoolSetting("Игроки", true));
    private final BoolSetting mobs = add(new BoolSetting("Мобы", true));
    private final BoolSetting animals = add(new BoolSetting("Животные", false));
    private final BoolSetting invisible = add(new BoolSetting("Невидимые", false));
    private final BoolSetting walls = add(new BoolSetting("Через стены", false));
    private final ModeSetting fx = add(new ModeSetting("Эффект цели", 2, "Кольца", "Бокс", "Кольца+Бокс", "Выкл"));

    // Всё остальное зашито: всегда с наведением, всегда криты, GCD и проверка луча включены.
    private static final double FOV = 360.0;
    private static final float ROT_SPEED = 70f;

    private static KillAura instance;

    /** Серверная (тихая) ротация: камера игрока не трогается, в пакеты движения подставляются эти углы. */
    public static volatile boolean silentActive;
    public static volatile float silentYaw, silentPitch;
    private static final Random RND = new Random();

    /** Текущая цель (для ESP/эффекта). */
    public static volatile LivingEntity current;
    /** Модуль Sprint не должен включать спринт, пока мы сбрасываем его ради крита. */
    public static volatile boolean suppressSprint;

    private static LivingEntity fxTarget;
    private static float fxAlpha;
    private int critWait;

    public KillAura() {
        super("KillAura", Category.COMBAT, "Автоатака ближайших целей");
        instance = this;
    }

    @Override
    protected void onDisable() {
        current = null;
        silentActive = false;
        fxTarget = null;
        fxAlpha = 0f;
        suppressSprint = false;
        critWait = 0;
    }

    @Override
    public void onTick() {
        suppressSprint = false;
        PlayerEntity p = mc.player;
        if (p == null || mc.world == null || mc.interactionManager == null) { current = null; silentActive = false; return; }
        if (mc.currentScreen != null || p.isUsingItem() || p.isSpectator()) { current = null; silentActive = false; tickFx(); return; }

        LivingEntity target = pickTarget(p);
        current = target;
        tickFx();
        if (target == null) { critWait = 0; silentActive = false; return; }

        boolean onTarget = rotateTo(p, target);
        boolean inReach = reach(p, target) <= range.get();
        float cd = p.getAttackCooldownProgress(0.5f);
        boolean critPossible = !p.isTouchingWater() && !p.isClimbing() && !p.hasVehicle()
                && !p.hasStatusEffect(StatusEffects.BLINDNESS) && !p.isInLava();

        if (!critPossible) {            // криты невозможны (вода, лестница...) — просто бьём по кулдауну
            if (onTarget && inReach && cd >= 0.96f) hit(p, target);
            return;
        }

        // Цель рядом, стоим на земле — прыгаем, удар придёт на падении.
        if (p.isOnGround() && inReach) {
            critWait++;
            if (cd >= 0.45f || critWait > 3) p.jump();
            // если прыгнуть не получается (потолок, паутина) — не стоим вечно, бьём обычным
            if (critWait > 10 && onTarget && cd >= 0.96f) { hit(p, target); }
            return;
        }

        if (!p.isOnGround()) {
            suppressSprint = true;                           // крит не засчитывается на спринте
            if (p.isSprinting()) p.setSprinting(false);
            boolean falling = p.fallDistance > 0.0F && p.getVelocity().y < 0.0;
            if (falling && onTarget && inReach && cd >= 0.93f) hit(p, target);
        }
    }

    private void hit(PlayerEntity p, LivingEntity target) {
        mc.interactionManager.attackEntity(p, target);
        p.swingHand(Hand.MAIN_HAND);
        critWait = 0;
    }

    /** Расстояние от глаз до ближайшей точки хитбокса (как считает сервер), а не между центрами. */
    private static double reach(PlayerEntity p, LivingEntity t) {
        Vec3d eye = p.getEyePos();
        Box b = t.getBoundingBox();
        double x = MathHelper.clamp(eye.x, b.minX, b.maxX);
        double y = MathHelper.clamp(eye.y, b.minY, b.maxY);
        double z = MathHelper.clamp(eye.z, b.minZ, b.maxZ);
        return eye.distanceTo(new Vec3d(x, y, z));
    }

    private boolean canCrit(PlayerEntity p) {
        return !p.isOnGround() && p.fallDistance > 0.0F && !p.isClimbing() && !p.isTouchingWater()
                && !p.hasStatusEffect(StatusEffects.BLINDNESS) && !p.hasVehicle() && !p.isSprinting();
    }

    // ---------------------------------------------------------------- ротации

    /** Двигает камеру к цели. Возвращает true, если можно бить (смотрим на хитбокс). */
    private boolean rotateTo(PlayerEntity p, LivingEntity t) {
        Vec3d eye = p.getEyePos();
        Vec3d pt = aimPoint(t, eye);
        double dx = pt.x - eye.x, dy = pt.y - eye.y, dz = pt.z - eye.z;
        double hd = Math.sqrt(dx * dx + dz * dz);
        float ty = (float) (Math.toDegrees(Math.atan2(dz, dx)) - 90.0);
        float tp = MathHelper.clamp((float) -Math.toDegrees(Math.atan2(dy, hd)), -90f, 90f);

        if (!silentActive) { silentYaw = p.getYaw(); silentPitch = p.getPitch(); silentActive = true; }
        float cy = silentYaw, cp = silentPitch;
        // Попадание проверяем по тем углам, что сервер видит СЕЙЧАС (ещё до доворота этого тика).
        boolean onNow;
        {
            Vec3d look0 = lookVec(cy, cp);
            Box b0 = t.getBoundingBox().expand(0.05);
            onNow = b0.contains(eye) || b0.raycast(eye, eye.add(look0.multiply(range.get() + 0.3))).isPresent();
        }
        float dyaw = MathHelper.wrapDegrees(ty - cy);
        float dpit = tp - cp;
        float sy, sp;
        float max = ROT_SPEED;

        switch (0) {
            case 0 -> { // Spooky: плавное затухающее наведение, шум, мёртвая зона, без снапов
                sy = MathHelper.clamp(dyaw * (0.55f + RND.nextFloat() * 0.12f), -max, max);
                sp = MathHelper.clamp(dpit * (0.45f + RND.nextFloat() * 0.10f), -max * 0.6f, max * 0.6f);
                if (Math.abs(dyaw) <= 0.35f) sy = 0f;
                else if (Math.abs(sy) < 0.35f) sy = Math.copySign(0.35f, dyaw);
                if (Math.abs(dpit) <= 0.3f) sp = 0f;
                else if (Math.abs(sp) < 0.3f) sp = Math.copySign(0.3f, dpit);
            }
            case 1 -> { // Плавная
                sy = MathHelper.clamp(dyaw * 0.5f, -max, max);
                sp = MathHelper.clamp(dpit * 0.5f, -max, max);
            }
            default -> { // Резкая
                sy = dyaw;
                sp = dpit;
            }
        }

        if (true) {
            float step = gcdStep();
            sy = Math.round(sy / step) * step;
            sp = Math.round(sp / step) * step;
        }

        silentYaw = cy + sy;
        silentPitch = MathHelper.clamp(cp + sp, -90f, 90f);
        return onNow;
    }

    private static Vec3d lookVec(float yaw, float pitch) {
        float f = pitch * 0.017453292F, g = -yaw * 0.017453292F;
        float h = MathHelper.cos(g), i = MathHelper.sin(g), j = MathHelper.cos(f), k = MathHelper.sin(f);
        return new Vec3d(i * j, -k, h * j);
    }

    /** Шаг мыши в градусах при текущей чувствительности (GCD ротаций, как у реального игрока). */
    private float gcdStep() {
        double s = mc.options.getMouseSensitivity().getValue() * 0.6 + 0.2;
        return (float) (s * s * s * 8.0 * 0.15);
    }

    private Vec3d aimPoint(LivingEntity t, Vec3d eye) {
        Box b = t.getBoundingBox();
        double h = b.maxY - b.minY;
        double cx = (b.minX + b.maxX) / 2.0 + (t.getX() - t.prevX) * 1.5;
        double cz = (b.minZ + b.maxZ) / 2.0 + (t.getZ() - t.prevZ) * 1.5;
        double y = MathHelper.clamp(eye.y, b.minY + h * 0.35, b.maxY - h * 0.12);
        if (true) {
            double ms = System.currentTimeMillis();
            double w = b.maxX - b.minX;
            cx += Math.sin(ms / 430.0) * w * 0.18;
            cz += Math.cos(ms / 510.0) * w * 0.18;
            y = MathHelper.clamp(y + Math.sin(ms / 370.0) * h * 0.05, b.minY + h * 0.3, b.maxY - h * 0.1);
        }
        return new Vec3d(cx, y, cz);
    }

    // ---------------------------------------------------------------- цели

    private boolean valid(PlayerEntity p, LivingEntity le) {
        if (le == p || !le.isAlive() || le instanceof ArmorStandEntity) return false;
        if (le.isInvisible() && !invisible.get()) return false;
        boolean ok = (le instanceof PlayerEntity pl && !pl.isSpectator() && players.get())
                || (le instanceof Monster && mobs.get())
                || (le instanceof PassiveEntity && animals.get());
        if (!ok) return false;
        if (reach(p, le) > scan.get()) return false;
        if (!walls.get() && !p.canSee(le)) return false;
        double yawTo = Math.toDegrees(Math.atan2(le.getZ() - p.getZ(), le.getX() - p.getX())) - 90.0;
        double diff = Math.abs(MathHelper.wrapDegrees((float) (yawTo - p.getYaw())));
        return diff <= FOV / 2.0;
    }

    private LivingEntity pickTarget(PlayerEntity p) {
        LivingEntity cur = current;
        if (cur != null && valid(p, cur)) return cur;   // фиксация на цели, без дёрганья между игроками

        LivingEntity best = null;
        double bestScore = Double.MAX_VALUE;
        for (Entity e : mc.world.getEntities()) {
            if (!(e instanceof LivingEntity le) || !valid(p, le)) continue;
            double dist = reach(p, le);
            double yawTo = Math.toDegrees(Math.atan2(le.getZ() - p.getZ(), le.getX() - p.getX())) - 90.0;
            double diff = Math.abs(MathHelper.wrapDegrees((float) (yawTo - p.getYaw())));
            double score = switch (priority.index()) {
                case 1 -> le.getHealth() + le.getAbsorptionAmount();
                case 2 -> diff;
                case 3 -> le.getArmor();
                default -> dist;
            };
            if (score < bestScore) { bestScore = score; best = le; }
        }
        return best;
    }

    // ---------------------------------------------------------------- эффект на цели

    private static void tickFx() {
        LivingEntity c = current;
        if (c != null) { fxTarget = c; fxAlpha = Math.min(1f, fxAlpha + 0.14f); }
        else { fxAlpha = Math.max(0f, fxAlpha - 0.08f); if (fxAlpha <= 0f) fxTarget = null; }
    }

    /** Вызывается из WorldRenderEvents.LAST. view — матрица вида, cam — позиция камеры. */
    public static void renderFx(Matrix4f view, Vec3d cam) {
        KillAura k = instance;
        LivingEntity t = fxTarget;
        if (k == null || !k.isEnabled() || t == null || fxAlpha <= 0f) return;
        int mode = k.fx.index();
        if (mode == 3) return;

        float pt = Render.partial();
        double x = t.prevX + (t.getX() - t.prevX) * pt;
        double y = t.prevY + (t.getY() - t.prevY) * pt;
        double z = t.prevZ + (t.getZ() - t.prevZ) * pt;
        double h = t.getHeight();
        double r = t.getWidth() * 0.5 + 0.32;
        double time = System.currentTimeMillis() / 1000.0;

        Render.beginFx();
        try {
            if (mode == 0 || mode == 2) {
                // две бегущие вверх-вниз радужные «ленты» + кольцо у ног
                for (int n = 0; n < 2; n++) {
                    double ph = time * 2.0 + n * Math.PI;
                    double s = Math.sin(ph);
                    double yy = y + h * (0.5 + 0.5 * s);
                    boolean up = Math.cos(ph) > 0;
                    band(view, cam, x, yy, z, r, 0.30, up, time, 210);
                }
                band(view, cam, x, y + 0.02, z, r + 0.04, 0.05, true, time * 0.7, 170);
            }
            if (mode == 1 || mode == 2) {
                Box bb = t.getBoundingBox().offset(x - t.getX(), y - t.getY(), z - t.getZ()).expand(0.03);
                shimmerBox(view, cam, bb, time);
            }
        } finally {
            Render.endFx();
        }
    }

    /** Кольцо-лента вокруг цели: яркий ведущий край, затухающий хвост, радужный перелив по окружности. */
    private static void band(Matrix4f m, Vec3d cam, double cx, double y, double cz, double r,
                             double bh, boolean up, double time, int alphaMax) {
        int seg = 40;
        BufferBuilder b = Tessellator.getInstance().begin(VertexFormat.DrawMode.TRIANGLE_STRIP, VertexFormats.POSITION_COLOR);
        int aLead = (int) (alphaMax * fxAlpha);
        for (int i = 0; i <= seg; i++) {
            double a = i * (Math.PI * 2 / seg);
            double px = cx + Math.cos(a) * r, pz = cz + Math.sin(a) * r;
            float hue = (float) (time * 0.25 + i / (double) seg);
            int lead = Render.hue(hue, aLead);
            int tail = Render.hue(hue, 0);
            double yTop = y + (up ? 0 : -bh), yBot = y + (up ? -bh : 0);
            // верхняя вершина / нижняя вершина; ведущий край — тот, что по направлению движения
            vtx(b, m, cam, px, up ? y : yTop, pz, up ? lead : tail);
            vtx(b, m, cam, px, up ? yBot : y, pz, up ? tail : lead);
        }
        BufferRenderer.drawWithGlobalProgram(b.end());
    }

    private static void shimmerBox(Matrix4f m, Vec3d cam, Box bb, double time) {
        BufferBuilder b = Tessellator.getInstance().begin(VertexFormat.DrawMode.QUADS, VertexFormats.POSITION_COLOR);
        double h = bb.maxY - bb.minY;
        double[][] c = {
                {bb.minX, bb.minZ}, {bb.maxX, bb.minZ}, {bb.maxX, bb.maxZ}, {bb.minX, bb.maxZ}
        };
        for (int i = 0; i < 4; i++) {
            double[] a = c[i], d = c[(i + 1) % 4];
            vtxBox(b, m, cam, a[0], bb.minY, a[1], bb.minY, h, time);
            vtxBox(b, m, cam, d[0], bb.minY, d[1], bb.minY, h, time);
            vtxBox(b, m, cam, d[0], bb.maxY, d[1], bb.minY, h, time);
            vtxBox(b, m, cam, a[0], bb.maxY, a[1], bb.minY, h, time);
        }
        // крышка
        for (double[] a : c) vtxBox(b, m, cam, a[0], bb.maxY, a[1], bb.minY, h, time);
        BufferRenderer.drawWithGlobalProgram(b.end());
    }

    private static void vtxBox(BufferBuilder b, Matrix4f m, Vec3d cam, double x, double y, double z,
                               double minY, double h, double time) {
        double rel = h <= 0 ? 0 : (y - minY) / h;
        // бегущий блик по высоте + радужный перелив
        double glint = Math.max(0.0, Math.sin(rel * 5.0 - time * 3.5));
        int alpha = (int) ((38 + 75 * glint) * fxAlpha);
        vtx(b, m, cam, x, y, z, Render.hue((float) (time * 0.2 + rel * 0.6 + (x + z) * 0.3), alpha));
    }

    private static void vtx(BufferBuilder b, Matrix4f m, Vec3d cam, double x, double y, double z, int argb) {
        b.vertex(m, (float) (x - cam.x), (float) (y - cam.y), (float) (z - cam.z)).color(argb);
    }
}
