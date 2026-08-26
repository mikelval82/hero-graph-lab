const navigation = globalThis.HeroNavigation;

export function continueJourney(relation) {
  return navigation.create(relation);
}

export function normalizeDirectly(relation) {
  return globalThis.HeroNavigation.normalizeRelation(relation);
}

export function callUnexported() {
  return navigation.privateHelper();
}

export function callUnknownGlobal() {
  return globalThis.UnknownNavigation.run();
}
