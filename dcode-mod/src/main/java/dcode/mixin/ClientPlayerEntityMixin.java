package dcode.mixin;

import dcode.module.KillAura;
import net.minecraft.client.network.ClientPlayerEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Тихая ротация: на время отправки пакетов движения подставляем углы KillAura, потом возвращаем камеру. */
@Mixin(ClientPlayerEntity.class)
public abstract class ClientPlayerEntityMixin {
    @Unique private float dcode$yaw, dcode$pitch;
    @Unique private boolean dcode$swapped;

    @Inject(method = "sendMovementPackets", at = @At("HEAD"))
    private void dcode$silentHead(CallbackInfo ci) {
        if (!KillAura.silentActive) return;
        ClientPlayerEntity self = (ClientPlayerEntity) (Object) this;
        dcode$yaw = self.getYaw();
        dcode$pitch = self.getPitch();
        self.setYaw(KillAura.silentYaw);
        self.setPitch(KillAura.silentPitch);
        dcode$swapped = true;
    }

    @Inject(method = "sendMovementPackets", at = @At("RETURN"))
    private void dcode$silentTail(CallbackInfo ci) {
        if (!dcode$swapped) return;
        ClientPlayerEntity self = (ClientPlayerEntity) (Object) this;
        self.setYaw(dcode$yaw);
        self.setPitch(dcode$pitch);
        dcode$swapped = false;
    }
}
