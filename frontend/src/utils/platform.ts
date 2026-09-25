/**
 * True only for an iOS home-screen PWA (standalone display mode). Firebase Auth's Google
 * sign-in is unreliable there: `signInWithRedirect` completes in Safari's own storage
 * partition, not the standalone app's, so the app loses the session on return.
 * Regular Safari and installed Android PWAs don't have this problem.
 */
export function isIosStandalonePwa(): boolean {
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isStandalone =
    (navigator as unknown as { standalone?: boolean }).standalone === true ||
    window.matchMedia("(display-mode: standalone)").matches;
  return isIos && isStandalone;
}
