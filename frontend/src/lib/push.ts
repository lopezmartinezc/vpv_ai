import { apiClient } from "@/lib/api-client";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const array = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; ++i) array[i] = raw.charCodeAt(i);
  return array;
}

export async function registerPushSubscription(): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.register("/sw.js");

    // Get VAPID public key from backend
    const { public_key } = await apiClient.get<{ public_key: string }>(
      "/notifications/vapid-public-key",
    );
    if (!public_key) return false;

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource,
    });

    const json = subscription.toJSON();
    if (!json.endpoint || !json.keys) return false;

    await apiClient.post("/notifications/subscribe", {
      endpoint: json.endpoint,
      p256dh: json.keys.p256dh,
      auth: json.keys.auth,
    });

    return true;
  } catch (err) {
    console.error("Push subscription failed:", err);
    return false;
  }
}

export function isPushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function isPushPermissionGranted(): boolean {
  return "Notification" in window && Notification.permission === "granted";
}

export function isPushPermissionDenied(): boolean {
  return "Notification" in window && Notification.permission === "denied";
}
