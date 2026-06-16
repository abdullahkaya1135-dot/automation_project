import { initLogin } from "./modules/login.js?v=20260612-refactor";

const page = document.body.dataset.page || "";

if (page === "login") {
  initLogin();
} else if (page === "operator") {
  const { initOperatorPage } = await import("./modules/pages/operator.js?v=20260615-shop-orders");
  initOperatorPage();
} else if (page === "utility") {
  const { initUtilityPage } = await import("./modules/pages/utility.js?v=20260615-pages");
  initUtilityPage();
} else if (page === "supervisor") {
  const { initSupervisorPage } = await import("./modules/pages/supervisor.js?v=20260615-pages");
  initSupervisorPage();
} else if (page === "planning") {
  const { initPlanningPage } = await import("./modules/pages/planning.js?v=20260615-pages");
  initPlanningPage();
}
