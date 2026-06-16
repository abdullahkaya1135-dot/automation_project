let currentShopOrderPairs = [];

export function shopOrderPairs() {
  return currentShopOrderPairs;
}

export function setShopOrderPairs(pairs) {
  currentShopOrderPairs = Array.isArray(pairs) ? pairs : [];
}

export function hasShopOrderPairs() {
  return currentShopOrderPairs.length > 0;
}

export function findShopOrderPair(key) {
  return currentShopOrderPairs.find((pair) => pair.key === key) || null;
}

export function orderOptionsForMachine(machine) {
  return currentShopOrderPairs.filter(
    (pair) => !machine || pair.resourceId === machine,
  );
}
