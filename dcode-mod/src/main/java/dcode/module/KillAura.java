package dcode.module;

import dcode.setting.BoolSetting;
import dcode.setting.ModeSetting;
import dcode.setting.NumSetting;
import net.minecraft.entity.Entity;
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.decoration.ArmorStandEntity;
import net.minecraft.entity.mob.Monster;
import net.minecraft.entity.passive.PassiveEntity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.Hand;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.Vec3d;

public class KillAura extends Module {
    private final NumSetting range = add(new NumSetting("Дистанция", 3.0, 2.0, 6.0, 0.1));
    private final NumSetting fov = add(new NumSetting("FOV", 360, 30, 360, 10));
    private final ModeSetting priority = add(new ModeSetting("Приоритет", 0, "Дистанция", "Здоровье", "Угол"));
    private final BoolSetting players = add(new BoolSetting("Игроки", true));
    private final BoolSetting mobs = add(new BoolSetting("Мобы", true));
    private final BoolSetting animals = add(new BoolSetting("Животные", false));
    private final BoolSetting invisible = add(new BoolSetting("Невидимые", false));
    private final BoolSetting walls = add(new BoolSetting("Через стены", false));
    private final BoolSetting rotate = add(new BoolSetting("Наведение", true));
    private final NumSetting rotSpeed = add(new NumSetting("Скорость наведения", 60, 10, 180, 5));
    private final NumSetting cooldown = add(new NumSetting("Кулдаун атаки", 0.95, 0.5, 1.0, 0.05));

    public KillAura() { super("KillAura", Category.COMBAT, "Автоатака ближайших целей"); }

    @Override
    public void onTick() {
        PlayerEntity p = mc.player;
        if (p == null || mc.world == null || mc.interactionManager == null) return;
        if (mc.currentScreen != null || p.isUsingItem() || p.isSpectator()) return;

        LivingEntity target = pickTarget(p);
        if (target == null) return;

        boolean aimed = true;
        if (rotate.get()) {
            Vec3d eye = p.getEyePos();
            double dx = target.getX() - eye.x;
            double dy = target.getY() + target.getHeight() * 0.6 - eye.y;
            double dz = target.getZ() - eye.z;
            double hd = Math.sqrt(dx * dx + dz * dz);
            float yaw = (float) (Math.toDegrees(Math.atan2(dz, dx)) - 90.0);
            float pitch = (float) -Math.toDegrees(Math.atan2(dy, hd));
            float sp = (float) rotSpeed.get();
            float dyaw = MathHelper.wrapDegrees(yaw - p.getYaw());
            float dpit = pitch - p.getPitch();
            aimed = Math.abs(dyaw) <= Math.max(sp, 5f) && Math.abs(dpit) <= Math.max(sp, 5f);
            p.setYaw(p.getYaw() + MathHelper.clamp(dyaw, -sp, sp));
            p.setPitch(MathHelper.clamp(p.getPitch() + MathHelper.clamp(dpit, -sp, sp), -90f, 90f));
        }

        if (aimed && p.getAttackCooldownProgress(0.5f) >= cooldown.get()) {
            mc.interactionManager.attackEntity(p, target);
            p.swingHand(Hand.MAIN_HAND);
        }
    }

    private LivingEntity pickTarget(PlayerEntity p) {
        LivingEntity best = null;
        double bestScore = Double.MAX_VALUE;
        for (Entity e : mc.world.getEntities()) {
            if (!(e instanceof LivingEntity le) || le == p || !le.isAlive() || le instanceof ArmorStandEntity) continue;
            if (le.isInvisible() && !invisible.get()) continue;
            boolean ok = (le instanceof PlayerEntity pl && !pl.isSpectator() && players.get())
                    || (le instanceof Monster && mobs.get())
                    || (le instanceof PassiveEntity && animals.get());
            if (!ok) continue;
            double dist = p.distanceTo(le);
            if (dist > range.get()) continue;
            if (!walls.get() && !p.canSee(le)) continue;
            double yawTo = Math.toDegrees(Math.atan2(le.getZ() - p.getZ(), le.getX() - p.getX())) - 90.0;
            double diff = Math.abs(MathHelper.wrapDegrees((float) (yawTo - p.getYaw())));
            if (diff > fov.get() / 2.0) continue;
            double score = switch (priority.index()) {
                case 1 -> le.getHealth();
                case 2 -> diff;
                default -> dist;
            };
            if (score < bestScore) { bestScore = score; best = le; }
        }
        return best;
    }
}
