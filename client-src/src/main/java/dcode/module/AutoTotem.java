package dcode.module;

import dcode.setting.NumSetting;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.Items;
import net.minecraft.screen.slot.SlotActionType;

public class AutoTotem extends Module {
    private final NumSetting health = add(new NumSetting("Здоровье (0 = всегда)", 0, 0, 20, 1));
    private final NumSetting delay = add(new NumSetting("Задержка (тики)", 1, 0, 10, 1));
    private int timer;

    public AutoTotem() { super("AutoTotem"); }

    @Override
    public void onTick() {
        PlayerEntity p = mc.player;
        if (p == null || mc.interactionManager == null) return;
        if (timer > 0) { timer--; return; }
        if (p.getOffHandStack().isOf(Items.TOTEM_OF_UNDYING)) return;
        if (health.getInt() > 0 && p.getHealth() + p.getAbsorptionAmount() > health.getInt()) return;
        for (int i = 0; i < 36; i++) {
            if (p.getInventory().getStack(i).isOf(Items.TOTEM_OF_UNDYING)) {
                int slot = i < 9 ? i + 36 : i;
                mc.interactionManager.clickSlot(p.playerScreenHandler.syncId, slot, 40, SlotActionType.SWAP, p);
                timer = delay.getInt();
                return;
            }
        }
    }
}
