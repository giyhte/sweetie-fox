package dev.pulselite;

import com.mojang.blaze3d.platform.InputConstants;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElementRegistry;
import net.fabricmc.fabric.api.client.rendering.v1.hud.VanillaHudElements;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.Identifier;
import net.fabricmc.fabric.api.client.message.v1.ClientReceiveMessageEvents;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
import org.lwjgl.glfw.GLFW;

public class PulseLiteClient implements ClientModInitializer {
    public static final String ID = "pulselite";
    public static KeyMapping OPEN_MENU;

    @Override
    public void onInitializeClient() {
        PulseConfig.load();
        KeyMapping.Category cat = KeyMapping.Category.register(Identifier.fromNamespaceAndPath(ID, "main"));
        OPEN_MENU = KeyBindingHelper.registerKeyBinding(
                new KeyMapping("key.pulselite.menu", InputConstants.Type.KEYSYM, GLFW.GLFW_KEY_RIGHT_SHIFT, cat));
        ClientTickEvents.END_CLIENT_TICK.register(PulseLiteClient::tick);
        ClientReceiveMessageEvents.GAME.register((msg, overlay) -> { if (!overlay) safeMessage(msg.getString()); });
        ClientReceiveMessageEvents.CHAT.register((msg, signed, sender, params, ts) -> safeMessage(msg.getString()));
        AttackEntityCallback.EVENT.register((player, level, hand, entity, hit) -> {
            if (level.isClientSide() && entity instanceof LivingEntity le) onHit(player, le);
            return InteractionResult.PASS;
        });
        HudElementRegistry.attachElementBefore(VanillaHudElements.CHAT,
                Identifier.fromNamespaceAndPath(ID, "hud"), PulseHud::render);
    }

    private static void safeMessage(String s) {
        try { PulseEvents.onMessage(s); } catch (Throwable t) { System.err.println("[PulseLite] event parse: " + t); }
    }

    private static LivingEntity lastTarget;
    private static long lastTargetTick;

    private static void onHit(net.minecraft.world.entity.player.Player p, LivingEntity le) {
        PulseConfig c = PulseConfig.get();
        lastTarget = le;
        lastTargetTick = System.currentTimeMillis();
        boolean crit = p.fallDistance > 0.0 && !p.onGround() && p.getAttackStrengthScale(0.5f) > 0.9f;
        if (crit && c.critSound) PulseSounds.playLib(c.critType, c.critVolume, c.critPitch);
        else if (c.hitSound) PulseSounds.playLib(c.hitType, c.hitVolume, c.hitPitch);
    }

    private static void tick(Minecraft mc) {
        try {
            PulseBoost.tick(mc);
        } catch (Throwable t) { System.err.println("[PulseLite] boost tick: " + t); }
        PulseConfig cf = PulseConfig.get();
        if (mc.player != null && lastTarget != null) {
            if (System.currentTimeMillis() - lastTargetTick > 1500) lastTarget = null;
            else if (lastTarget.isDeadOrDying() || lastTarget.isRemoved()) {
                if (cf.killSound) PulseSounds.playLib(cf.killType, cf.killVolume, cf.killPitch);
                lastTarget = null;
            }
        }
        while (OPEN_MENU.consumeClick()) {
            if (mc.screen == null) { PulseSounds.ui("ui_open"); mc.setScreen(new PulseMenuScreen(null)); }
        }
    }
}
