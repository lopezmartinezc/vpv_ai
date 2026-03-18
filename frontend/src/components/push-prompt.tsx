"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import {
  isPushPermissionDenied,
  isPushPermissionGranted,
  isPushSupported,
  registerPushSubscription,
} from "@/lib/push";

export function PushPrompt() {
  const { user } = useAuth();
  const [show, setShow] = useState(false);
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (!isPushSupported()) return;
    if (isPushPermissionGranted() || isPushPermissionDenied()) return;

    // Check if already dismissed this session
    const dismissed = sessionStorage.getItem("push_prompt_dismissed");
    if (dismissed) return;

    // Show prompt after a short delay
    const timer = setTimeout(() => setShow(true), 3000);
    return () => clearTimeout(timer);
  }, [user]);

  if (!show) return null;

  async function handleEnable() {
    setRegistering(true);
    const permission = await Notification.requestPermission();
    if (permission === "granted") {
      await registerPushSubscription();
    }
    setShow(false);
    setRegistering(false);
  }

  function handleDismiss() {
    sessionStorage.setItem("push_prompt_dismissed", "1");
    setShow(false);
  }

  return (
    <div className="border-b border-blue-600/30 bg-blue-600/10 px-4 py-2 text-center text-sm">
      <span className="text-vpv-text">
        Activa las notificaciones para recibir recordatorios de alineacion
      </span>
      <button
        onClick={handleEnable}
        disabled={registering}
        className="ml-3 rounded bg-blue-600 px-2 py-0.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
      >
        {registering ? "Activando..." : "Activar"}
      </button>
      <button
        onClick={handleDismiss}
        className="ml-2 text-xs text-vpv-text-muted hover:text-vpv-text"
      >
        Ahora no
      </button>
    </div>
  );
}
