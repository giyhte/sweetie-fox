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
    public static KeyMapping ZOOM;
    private static boolean zooming = false;
    private static int savedFov = 70;

    @Override
    public void onInitializeClient() {
        PulseConfig.load();
        KeyMapping.Category cat = KeyMapping.Category.register(Identifier.fromNamespaceAndPath(ID, "main"));
        OPEN_MENU = KeyBindingHelper.registerKeyBinding(
                new KeyMapping("key.pulselite.menu", InputConstants.Type.KEYSYM, GLFW.GLFW_KEY_RIGHT_SHIFT, cat));
        ZOOM = KeyBindingHelper.registerKeyBinding(
                new KeyMapping("key.pulselite.zoom", InputConstants.Type.KEYSYM, GLFW.GLFW_KEY_C, cat));
        ClientTickEvents.END_CLIENT_TICK.register(PulseLiteClient::tick);
        ClientReceiveMessageEvents.GAME.register((msg, overlay) -> { if (!overlay) PulseEvents.onMessage(msg.getString()); });
        ClientReceiveMessageEvents.CHAT.register((msg, signed, sender, params, ts) -> PulseEvents.onMessage(msg.getString()));
        AttackEntityCallback.EVENT.register((player, level, hand, entity, hit) -> {
            if (level.isClientSide() && entity instanceof LivingEntity le) onHit(player, le);
            return InteractionResult.PASS;
        });
        HudElementRegistry.attachElementBefore(VanillaHudElements.CHAT,
                Identifier.fromNamespaceAndPath(ID, "hud"), PulseHud::render);
    }

    private static LivingEntity lastTarget;
    private static long lastTargetTick;
    private static boolean sprintForced;
    private static int lastHurt;

    private static void onHit(net.minecraft.world.entity.player.Player p, LivingEntity le) {
        PulseConfig c = PulseConfig.get();
        lastTarget = le;
        lastTargetTick = System.currentTimeMillis();
        if (!c.hitSound) return;
        boolean crit = c.critSound && p.fallDistance > 0.0 && !p.onGround() && p.getAttackStrengthScale(0.5f) > 0.9f;
        float pitch = 0.95f + (float) Math.random() * 0.15f;
        PulseSounds.play(crit ? "hit_crit" : PulseSounds.HIT_IDS[Math.floorMod(c.hitType, PulseSounds.HIT_IDS.length)], pitch, c.hitVolume / 100f);
    }

    private static void tick(Minecraft mc) {
        PulseConfig cf = PulseConfig.get();
        if (mc.player != null) {
            if (cf.autoSprint && mc.screen == null) {
                boolean go = mc.options.keyUp.isDown() && !mc.options.keyShift.isDown() && !mc.player.isUsingItem()
                        && mc.player.getFoodData().getFoodLevel() > 6;
                if (go) { mc.options.keySprint.setDown(true); sprintForced = true; }
                else if (sprintForced) { mc.options.keySprint.setDown(false); sprintForced = false; }
            }
            if (lastTarget != null) {
                if (System.currentTimeMillis() - lastTargetTick > 1500) lastTarget = null;
                else if (lastTarget.isDeadOrDying() || lastTarget.isRemoved()) {
                    if (cf.killSound) PulseSounds.play("kill", 1f, cf.hitVolume / 100f);
                    lastTarget = null;
                }
            }
            int h = mc.player.hurtTime;
            if (cf.hurtSound && h > 0 && lastHurt == 0) PulseSounds.play("hurt", 1f, 0.8f);
            lastHurt = h;
        }
        while (OPEN_MENU.consumeClick()) {
            if (mc.screen == null) { PulseSounds.ui("ui_open"); mc.setScreen(new PulseMenuScreen(null)); }
        }
        boolean want = PulseConfig.get().zoom && ZOOM.isDown() && mc.screen == null;
        if (want && !zooming) {
            savedFov = mc.options.fov().get();
            zooming = true;
        }
        if (want) {
            mc.options.fov().set(PulseConfig.get().zoomFov);
        } else if (zooming) {
            mc.options.fov().set(savedFov);
            zooming = false;
        }
    }
}
