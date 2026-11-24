package dcode.module;

import dcode.mixin.EntityAccessor;
import dcode.setting.BoolSetting;
import dcode.setting.NumSetting;
import net.minecraft.entity.Entity;
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.mob.Monster;
import net.minecraft.entity.passive.PassiveEntity;
import net.minecraft.entity.player.PlayerEntity;

import java.util.HashSet;
import java.util.Set;

/** ESP через штатную подсветку (контур виден сквозь стены). */
public class Esp extends Module {
    private final BoolSetting players = add(new BoolSetting("Игроки", true));
    private final BoolSetting mobs = add(new BoolSetting("Мобы", false));
    private final BoolSetting animals = add(new BoolSetting("Животные", false));
    private final NumSetting dist = add(new NumSetting("Дистанция", 64, 8, 128, 8));
    private final Set<Entity> marked = new HashSet<>();

    public Esp() { super("ESP"); }

    @Override
    public void onTick() {
        if (mc.world == null || mc.player == null) return;
        Set<Entity> now = new HashSet<>();
        for (Entity e : mc.world.getEntities()) {
            if (!(e instanceof LivingEntity) || e == mc.player) continue;
            boolean ok = (e instanceof PlayerEntity && players.get())
                    || (e instanceof Monster && mobs.get())
                    || (e instanceof PassiveEntity && animals.get());
            if (ok && mc.player.distanceTo(e) <= dist.get()) {
                ((EntityAccessor) e).dcode$setFlag(6, true);
                now.add(e);
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
}
