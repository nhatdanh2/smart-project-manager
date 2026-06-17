/**
 * Expo push notification token registrar.
 *
 * 1. On mount, ask the OS for permission and grab the token.
 * 2. POST it to ``/api/push/tokens`` so the backend can target
 *    this device with Web + mobile pushes.
 * 3. Listen for incoming notifications (foreground + tapped) and
 *    re-route to the right screen.
 *
 * Mounted once at the root layout.
 */
import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";

import { api } from "@/lib/api";
import { useAuth } from "@/providers/AuthProvider";


Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});


export function PushTokenRegistrar() {
  const { user } = useAuth();
  const router = useRouter();
  const responseListener = useRef<Notifications.Subscription>();
  const notificationListener = useRef<Notifications.Subscription>();

  useEffect(() => {
    if (!user) return;

    (async () => {
      try {
        if (!Device.isDevice) return;
        const { status: existing } = await Notifications.getPermissionsAsync();
        let granted = existing === "granted";
        if (!granted) {
          const { status } = await Notifications.requestPermissionsAsync();
          granted = status === "granted";
        }
        if (!granted) return;

        if (Platform.OS === "android") {
          await Notifications.setNotificationChannelAsync("default", {
            name: "default",
            importance: Notifications.AndroidImportance.MAX,
            vibrationPattern: [0, 250, 250, 250],
          });
        }
        const tokenData = await Notifications.getExpoPushTokenAsync();
        await api.post("/api/push/tokens", {
          token: tokenData.data,
          platform: Platform.OS,
          device_name: Device.deviceName,
        });
      } catch (err) {
        // Don't crash the app on push setup failure
        console.warn("push token registrar failed:", err);
      }
    })();

    notificationListener.current = Notifications.addNotificationReceivedListener(
      (notif) => {
        const data = (notif.request.content.data ?? {}) as { link?: string };
        if (data.link) {
          // Will be picked up by the response listener if user taps;
          // for foreground we just update the inbox in the background.
        }
      }
    );
    responseListener.current = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const data = (response.notification.request.content.data ?? {}) as { link?: string };
        if (data.link) router.push(data.link as any);
      }
    );

    return () => {
      responseListener.current?.remove();
      notificationListener.current?.remove();
    };
  }, [user, router]);

  return null;
}
