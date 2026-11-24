package dcode.module;

public class Sprint extends Module {
    public Sprint() { super("Sprint"); }

    @Override
    public void onTick() {
        if (mc.player == null) return;
        if (mc.player.input.movementForward > 0 && !mc.player.horizontalCollision
                && mc.player.getHungerManager().getFoodLevel() > 6) {
            mc.player.setSprinting(true);
        }
    }
}
