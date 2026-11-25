package dcode.module;

import dcode.Render;
import dcode.mixin.EntityAccessor;
import dcode.setting.BoolSetting;
import dcode.setting.ModeSetting;
import dcode.setting.NumSetting;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.entity.Entity;
import net.minecraft.entity.EquipmentSlot;
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.mob.Monster;
import net.minecraft.entity.passive.PassiveEntity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.ItemStack;
import net.minecraft.util.math.Box;

import java.awt.Color;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 2D ESP: рамка, полоска здоровья, ник, броня с прочностью. Рисуется поверх мира через проекцию. */
public class Esp extends Module {
    private final BoolSetting players = add(new BoolSetting("Игроки", true));
    private final BoolSetting mobs = add(new BoolSetting("Мобы", false));
    private final BoolSetting animals = add(new BoolSetting("Животные", false));
    private final NumSetting dist = add(new NumSetting("Дистанция", 64, 8, 128, 8));
    private final ModeSetting frame = add(new ModeSetting("Рамка", 0, "Углы", "Полная", "Выкл"));
    private final BoolSetting fill = add(new BoolSetting("Заливка", true));
    private final BoolSetting name = add(new BoolSetting("Ник", true));
    private final BoolSetting health = add(new BoolSetting("Здоровье", true));
    private final BoolSetting armor = add(new BoolSetting("Броня", true));
    private final BoolSetting hands = add(new BoolSetting("Предметы в руках", true));
    private final BoolSetting durability = add(new BoolSetting("Прочность", true));
    private final BoolSetting glow = add(new BoolSetting("Контур (glow)", false));
    private final Set<Entity> marked = new HashSet<>();

    private static final EquipmentSlot[] ARMOR = {
            EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET};

    public Esp() {
        super("ESP", Category.RENDER, "Рамка, здоровье и броня игроков");
        HudRenderCallback.EVENT.register(this::render);
    }

    private boolean accept(Entity e) {
        if (!(e instanceof LivingEntity) || e == mc.player || !e.isAlive()) return false;
        return (e instanceof PlayerEntity && players.get())
                || (e instanceof Monster && mobs.get())
                || (e instanceof PassiveEntity && animals.get());
    }

    @Override
    public void onTick() {
        if (mc.world == null || mc.player == null) return;
        Set<Entity> now = new HashSet<>();
        if (glow.get()) {
            for (Entity e : mc.world.getEntities()) {
                if (accept(e) && mc.player.distanceTo(e) <= dist.get()) {
                    ((EntityAccessor) e).dcode$setFlag(6, true);
                    now.add(e);
                }
            }
        }
        for (Entity e : marked) if (!now.contains(e)) ((EntityAccessor) e).dcode$setFlag(6, false);
        marked.clear();
        marked.addAll(now);
    }

    @Override
    protected void onDisable() {
        for (Entity e : marked) ((EntityAccessor) e).dcode$setFlag(6, false);
        marked.clear();
    }

    // ------------------------------------------------------------------ рендер

    private void render(DrawContext ctx, RenderTickCounter tick) {
        if (!isEnabled() || mc.world == null || mc.player == null || mc.options.hudHidden || !Render.ready) return;
        List<LivingEntity> list = new ArrayList<>();
        for (Entity e : mc.world.getEntities()) {
            if (accept(e) && mc.player.distanceTo(e) <= dist.get()) list.add((LivingEntity) e);
        }
        list.sort((a, b) -> Double.compare(mc.player.squaredDistanceTo(b), mc.player.squaredDistanceTo(a)));
        float pt = Render.partial();
        for (LivingEntity e : list) {
            try { drawEntity(ctx, e, pt); } catch (Throwable ignored) {}
        }
    }

    private void drawEntity(DrawContext ctx, LivingEntity e, float pt) {
        TextRenderer tr = mc.textRenderer;
        int sw = ctx.getScaledWindowWidth(), sh = ctx.getScaledWindowHeight();

        double lx = e.prevX + (e.getX() - e.prevX) * pt;
        double ly = e.prevY + (e.getY() - e.prevY) * pt;
        double lz = e.prevZ + (e.getZ() - e.prevZ) * pt;
        Box bb = e.getBoundingBox().offset(lx - e.getX(), ly - e.getY(), lz - e.getZ());

        float minX = Float.MAX_VALUE, minY = Float.MAX_VALUE, maxX = -Float.MAX_VALUE, maxY = -Float.MAX_VALUE;
        double[] xs = {bb.minX, bb.maxX}, ys = {bb.minY, bb.maxY}, zs = {bb.minZ, bb.maxZ};
        for (double x : xs) for (double y : ys) for (double z : zs) {
            float[] s = Render.project(x, y, z, sw, sh);
            if (s == null) return;
            minX = Math.min(minX, s[0]); maxX = Math.max(maxX, s[0]);
            minY = Math.min(minY, s[1]); maxY = Math.max(maxY, s[1]);
        }
        int x1 = Math.round(minX), y1 = Math.round(minY), x2 = Math.round(maxX), y2 = Math.round(maxY);
        int w = x2 - x1, h = y2 - y1;
        if (w < 3 || h < 3 || x2 < -50 || x1 > sw + 50 || y2 < -50 || y1 > sh + 50) return;

        boolean target = e == KillAura.current;
        int col;
        if (target) {
            float pulse = 0.5f + 0.5f * (float) Math.sin(System.currentTimeMillis() / 140.0);
            col = lerp(0xFFFF3B5C, 0xFFFFB3C0, pulse);
        } else if (e instanceof PlayerEntity) col = Hud.accent(0f);
        else if (e instanceof Monster) col = 0xFFFF7A45;
        else col = 0xFF5CE08A;

        // --- заливка и рамка
        if (fill.get()) ctx.fillGradient(x1, y1, x2, y2, (col & 0xFFFFFF) | 0x30000000, (col & 0xFFFFFF) | 0x0A000000);
        int len = Math.max(4, Math.min(w, h) / 4);
        if (frame.index() == 0) {
            brackets(ctx, x1, y1, x2, y2, len + 2, 3, 0xD0000000, 1);
            brackets(ctx, x1, y1, x2, y2, len, 1, col, 0);
        } else if (frame.index() == 1) {
            box(ctx, x1 - 1, y1 - 1, x2 + 1, y2 + 1, 3, 0xD0000000);
            box(ctx, x1, y1, x2, y2, 1, col);
        }

        // --- здоровье
        if (health.get()) {
            float max = Math.max(1f, e.getMaxHealth());
            float hp = Math.max(0f, e.getHealth());
            float ratio = Math.min(1f, hp / max);
            int bx = x1 - 5;
            ctx.fill(bx - 1, y1 - 1, bx + 3, y2 + 1, 0xD0000000);
            ctx.fill(bx, y1, bx + 2, y2, 0xFF1B1B22);
            int fh = Math.max(1, Math.round(h * ratio));
            int hc = Color.HSBtoRGB(ratio * 0.33f, 0.85f, 1f) | 0xFF000000;
            ctx.fillGradient(bx, y2 - fh, bx + 2, y2, hc, lerp(hc, 0xFF000000, 0.45f));
            float ab = e.getAbsorptionAmount();
            if (ab > 0) {
                int ah = Math.max(1, Math.round(h * Math.min(1f, ab / max)));
                ctx.fill(bx + 2, y2 - ah, bx + 3, y2, 0xFFFFD34D);
            }
        }

        // --- ник / HP / броня-очки
        if (name.get()) {
            float sc = 0.85f;
            String nm = e.getName().getString();
            String hpS = String.format("%.1f", e.getHealth() + e.getAbsorptionAmount());
            int arm = e.getArmor();
            String armS = arm > 0 ? "  \u0411\u0420 " + arm : "";
            String dS = "  " + Math.round(mc.player.distanceTo(e)) + "\u043c";
            int tw = Math.round((tr.getWidth(nm) + tr.getWidth("  " + hpS) + tr.getWidth(armS) + tr.getWidth(dS)) * sc);
            int th = Math.round(9 * sc) + 3;
            int tx = (x1 + x2) / 2 - tw / 2 - 3;
            int ty = y1 - th - 3;
            ctx.fill(tx, ty, tx + tw + 6, ty + th, 0xB0101018);
            ctx.fillGradient(tx, ty + th - 1, tx + tw + 6, ty + th, col, (col & 0xFFFFFF) | 0x40000000);
            float cx = tx + 3, cy = ty + 2;
            cx = text(ctx, tr, nm, cx, cy, sc, 0xFFFFFFFF);
            cx = text(ctx, tr, "  " + hpS, cx, cy, sc, Color.HSBtoRGB(Math.min(1f, e.getHealth() / Math.max(1f, e.getMaxHealth())) * 0.33f, 0.7f, 1f) | 0xFF000000);
            if (arm > 0) cx = text(ctx, tr, armS, cx, cy, sc, 0xFF7FD6FF);
            text(ctx, tr, dS, cx, cy, sc, 0xFF9A9AB0);
        }

        // --- броня и предметы в руках
        if (armor.get() || hands.get()) {
            List<ItemStack> items = new ArrayList<>();
            if (armor.get()) for (EquipmentSlot s : ARMOR) { ItemStack st = e.getEquippedStack(s); if (!st.isEmpty()) items.add(st); }
            if (hands.get()) {
                ItemStack m = e.getEquippedStack(EquipmentSlot.MAINHAND), o = e.getEquippedStack(EquipmentSlot.OFFHAND);
                if (!m.isEmpty()) items.add(m);
                if (!o.isEmpty()) items.add(o);
            }
            if (!items.isEmpty()) drawItems(ctx, tr, items, (x1 + x2) / 2, y2 + 3);
        }
    }

    private void drawItems(DrawContext ctx, TextRenderer tr, List<ItemStack> items, int cx, int y) {
        final float sc = 0.65f;
        final int step = 12;
        int total = items.size() * step;
        int sx = cx - total / 2;
        int rowH = 12 + (durability.get() ? 6 : 0);
        ctx.fill(sx - 2, y - 1, sx + total, y + rowH - 1, 0xA0101018);
        MatrixStack m = ctx.getMatrices();
        for (int i = 0; i < items.size(); i++) {
            ItemStack st = items.get(i);
            int ix = sx + i * step;
            m.push();
            m.translate(ix, y, 0);
            m.scale(sc, sc, 1f);
            ctx.drawItem(st, 0, 0);
            ctx.drawStackOverlay(tr, st, 0, 0);
            m.pop();
            if (durability.get() && st.isDamageable()) {
                int max = st.getMaxDamage();
                int pct = Math.max(0, Math.round(100f * (max - st.getDamage()) / Math.max(1, max)));
                int c = Color.HSBtoRGB(pct / 100f * 0.33f, 0.75f, 1f) | 0xFF000000;
                text(ctx, tr, String.valueOf(pct), ix, y + 11, 0.5f, c);
            }
        }
    }

    // ------------------------------------------------------------------ рисовалки

    private static float text(DrawContext c, TextRenderer tr, String s, float x, float y, float sc, int col) {
        MatrixStack m = c.getMatrices();
        m.push();
        m.translate(x, y, 0);
        m.scale(sc, sc, 1f);
        c.drawText(tr, s, 0, 0, col, true);
        m.pop();
        return x + tr.getWidth(s) * sc;
    }

    private static void brackets(DrawContext c, int x1, int y1, int x2, int y2, int len, int t, int col, int off) {
        x1 -= off; y1 -= off; x2 += off; y2 += off;
        c.fill(x1, y1, x1 + len, y1 + t, col);   c.fill(x1, y1, x1 + t, y1 + len, col);
        c.fill(x2 - len, y1, x2, y1 + t, col);   c.fill(x2 - t, y1, x2, y1 + len, col);
        c.fill(x1, y2 - t, x1 + len, y2, col);   c.fill(x1, y2 - len, x1 + t, y2, col);
        c.fill(x2 - len, y2 - t, x2, y2, col);   c.fill(x2 - t, y2 - len, x2, y2, col);
    }

    private static void box(DrawContext c, int x1, int y1, int x2, int y2, int t, int col) {
        c.fill(x1, y1, x2, y1 + t, col);
        c.fill(x1, y2 - t, x2, y2, col);
        c.fill(x1, y1, x1 + t, y2, col);
        c.fill(x2 - t, y1, x2, y2, col);
    }

    private static int lerp(int a, int b, float t) {
        int r = (int) (((a >> 16) & 255) + ((((b >> 16) & 255) - ((a >> 16) & 255)) * t));
        int g = (int) (((a >> 8) & 255) + ((((b >> 8) & 255) - ((a >> 8) & 255)) * t));
        int bl = (int) ((a & 255) + (((b & 255) - (a & 255)) * t));
        return 0xFF000000 | (r << 16) | (g << 8) | bl;
    }
}
