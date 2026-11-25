package dcode.module;

public class Sprint extends Module {
    public Sprint() { super("Sprint", Category.MOVEMENT, "Автоматический спринт"); }

    @Override
    public void onTick() {
        if (mc.player == null || KillAura.suppressSprint) return;
        if (mc.player.input.movementForward > 0 && !mc.player.horizontalCollision
                && mc.player.getHungerManager().getFoodLevel() > 6) {
            mc.player.setSprinting(true);
        }
    }
}
