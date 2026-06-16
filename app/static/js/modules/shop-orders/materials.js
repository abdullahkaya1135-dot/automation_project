import { apiJson } from "../../api.js?v=20260612-refactor";
import {
  cleanOptional,
  setInputValue,
  setMessage,
  uniqueSorted,
} from "../utils.js?v=20260612-refactor";

export function clearOperationPrefills() {
  setInputValue("#product-name", "");
  setInputValue("#raw-material", "");
  setMaterialOptions([]);
}

export async function applyOperationDetails(option) {
  if (!option) {
    clearOperationPrefills();
    return;
  }

  setInputValue("#product-name", productTextForOption(option));
  await prefillRawMaterial(option);
}

function productTextForOption(option) {
  if (!option) {
    return "";
  }
  if (option.partNo && option.partDescription?.startsWith(option.partNo)) {
    return option.partDescription;
  }
  return [option.partNo, option.partDescription].filter(Boolean).join(" - ");
}

async function prefillRawMaterial(option) {
  const rawMaterialInput = document.querySelector("#raw-material");
  if (!rawMaterialInput || !option || !option.operationNo) {
    setMaterialOptions([]);
    return;
  }
  rawMaterialInput.value = "";

  const query = new URLSearchParams({
    order_no: option.orderNo,
    release_no: option.releaseNo || "*",
    sequence_no: option.sequenceNo || "*",
    operation_no: String(option.operationNo),
  });

  try {
    const payload = await apiJson(`/api/ifs/operation-hm02-materials?${query}`);
    const partNumbers = uniqueSorted(
      (Array.isArray(payload.materials) ? payload.materials : [])
        .map((material) => cleanOptional(material.part_no)),
    );
    setMaterialOptions(partNumbers);
    if (partNumbers.length === 1) {
      rawMaterialInput.value = partNumbers[0];
    }
  } catch (error) {
    setMaterialOptions([]);
    setMessage(
      document.querySelector("#entry-message"),
      `Hammadde otomatik al\u0131namad\u0131; elle girebilirsiniz. ${error.message}`,
      "warning",
    );
  }
}

function setMaterialOptions(partNumbers) {
  const dataList = document.querySelector("#raw-material-options");
  if (!dataList) {
    return;
  }
  dataList.replaceChildren(
    ...partNumbers.map((partNumber) => new Option(partNumber, partNumber)),
  );
}
