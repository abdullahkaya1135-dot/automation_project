import { apiJson } from "../api.js?v=20260629-label-material-availability-v1";
import {
  renderLabelMaterialAvailability,
  renderListError,
  renderLoading,
} from "./render.js?v=20260629-label-material-availability-v1";
import { setButtonBusy, setMessage } from "./utils.js?v=20260629-label-material-availability-v1";

export async function handleLabelMaterialAvailability(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#label-material-availability-message");
  const container = document.querySelector("#label-material-availability-results");

  setMessage(message, "Label malzeme uygunluk kontrolu calisiyor...", "");
  renderLoading(container, "Aktif IFS operasyonlari, malzeme satirlari ve U1 stoklari okunuyor...");
  setButtonBusy(button, true, "Kontrol ediliyor");

  try {
    const payload = await apiJson("/api/ifs/label-material-availability");
    renderLabelMaterialAvailability(container, payload);

    const summary = payload?.summary || {};
    const checkedCount = Number(summary.checked_row_count || 0);
    const blockedCount = Number(summary.blocked_row_count || 0);
    if (blockedCount > 0) {
      setMessage(
        message,
        `${checkedCount} satir kontrol edildi. ${blockedCount} satir U1 uygunluk uyarisi veriyor.`,
        "warning",
      );
    } else if (checkedCount > 0) {
      setMessage(
        message,
        `${checkedCount} satir kontrol edildi. U1 uygunluk uyarisi yok.`,
        "success",
      );
    } else {
      setMessage(message, "Kontrol edilecek aktif HM/YM malzeme satiri bulunmadi.", "warning");
    }
  } catch (error) {
    setMessage(
      message,
      `Label malzeme uygunluk kontrolu basarisiz: ${error.message}`,
      "error",
    );
    renderListError(
      container,
      `Label malzeme uygunluk kontrolu basarisiz: ${error.message}`,
    );
  } finally {
    setButtonBusy(button, false);
  }
}
