import { apiJson } from "../../api.js?v=20260612-refactor";
import {
  loadAuxiliarySubmissions,
  loadEntryLists,
} from "../lists.js?v=20260612-refactor";
import { loadExcelPendingCount } from "../offline/status.js?v=20260616-offline-split";
import {
  setButtonBusy,
  setMessage,
} from "../utils.js?v=20260612-refactor";

export function bindSupervisorSyncControls({ refreshBootstrap }) {
  const retryButton = document.querySelector("#retry-sync");
  if (retryButton) {
    retryButton.addEventListener("click", (event) => {
      void handleRetrySync(event, refreshBootstrap);
    });
  }

  const auxiliaryRetryButton = document.querySelector("#retry-auxiliary-sync");
  if (auxiliaryRetryButton) {
    auxiliaryRetryButton.addEventListener("click", (event) => {
      void handleRetryAuxiliarySync(event, refreshBootstrap);
    });
  }
}

async function handleRetrySync(event, refreshBootstrap) {
  const button = event.currentTarget;
  const message = document.querySelector("#sync-message");

  setMessage(message, "Bekleyen Excel senkronizasyonu tekrar deneniyor...", "");
  setButtonBusy(button, true, "Deneniyor");

  try {
    const payload = await apiJson("/api/sync/retry", {
      method: "POST",
    });

    if (payload.failed) {
      setMessage(
        message,
        `Tekrar deneme ${payload.synced} senkronizasyon ve ${payload.failed} hata sonrasi durdu. ${payload.remaining} kayit bekliyor.`,
        "warning",
      );
    } else {
      setMessage(
        message,
        `Tekrar deneme tamamlandi. ${payload.synced} kayit senkronize edildi, ${payload.remaining} kayit bekliyor.`,
        "success",
      );
    }

    await Promise.all([
      loadEntryLists(),
      refreshBootstrap(),
      loadExcelPendingCount(),
    ]);
  } catch (error) {
    setMessage(message, `Tekrar deneme basarisiz: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function handleRetryAuxiliarySync(event, refreshBootstrap) {
  const button = event.currentTarget;
  const message = document.querySelector("#auxiliary-message");

  setMessage(message, "Yardimci sistemler Excel senkronizasyonu tekrar deneniyor...", "");
  setButtonBusy(button, true, "Deneniyor");

  try {
    const payload = await apiJson("/api/auxiliary-systems/sync/retry", {
      method: "POST",
    });

    if (payload.failed) {
      setMessage(
        message,
        `Tekrar deneme ${payload.synced} senkronizasyon ve ${payload.failed} hata sonrasi durdu. ${payload.remaining} gonderim bekliyor.`,
        "warning",
      );
    } else {
      setMessage(
        message,
        `Tekrar deneme tamamlandi. ${payload.synced} gonderim senkronize edildi, ${payload.remaining} gonderim bekliyor.`,
        "success",
      );
    }

    await Promise.all([
      loadAuxiliarySubmissions(),
      refreshBootstrap(),
      loadExcelPendingCount(),
    ]);
  } catch (error) {
    setMessage(message, `Tekrar deneme basarisiz: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}
