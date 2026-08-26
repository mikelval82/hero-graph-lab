((globalScope) => {
  function normalizeRelation(relation) {
    return relation || null;
  }

  function createStep(relation) {
    return normalizeRelation(relation);
  }

  function privateHelper() {
    function nestedHelper() {
      return "nested";
    }
    return nestedHelper();
  }

  const api = Object.freeze({
    normalizeRelation,
    create: createStep,
  });

  globalScope.HeroNavigation = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis === "undefined" ? this : globalThis);
