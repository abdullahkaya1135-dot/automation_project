import { apiJson } from "../../api.js?v=20260612-refactor";
import {
  setButtonBusy,
  setMessage,
} from "../utils.js?v=20260612-refactor";

export async function handleCreateCycleReport(event) {
  const button = event.currentTarget;
  const message = document.querySelector("#cycle-report-message");

  setMessage(message, "Cevrim kontrol raporu olusturuluyor...", "");
  setButtonBusy(button, true, "Olusturuluyor");

  try {
    const payload = await apiJson("/api/cycle-report/today", {
      method: "POST",
    });
    const warningText = payload.warning_count
      ? ` ${payload.warning_count} uyari var.`
      : "";
    setMessage(
      message,
      `Rapor olusturuldu: ${payload.output_path}. ${payload.row_count} kayit islendi.${warningText}`,
      payload.warning_count ? "warning" : "success",
    );
  } catch (error) {
    setMessage(message, `Rapor olusturulamadi: ${error.message}`, "error");
  } finally {
    setButtonBusy(button, false);
  }
}
