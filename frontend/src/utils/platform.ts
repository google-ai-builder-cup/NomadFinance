function isIos(): boolean {
  const ua = navigator.userAgent;
  // iPadOS Safari reports itself as a Mac; the touch screen gives it away.
  return /iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
}

function isStandalone(): boolean {
  return (
    (navigator as unknown as { standalone?: boolean }).standalone === true ||
    window.matchMedia("(display-mode: standalone)").matches
  );
}

/**
 * True only for an iOS home-screen PWA (standalone display mode). Firebase Auth's Google
 * sign-in is unreliable there: `signInWithRedirect` completes in Safari's own storage
 * partition, not the standalone app's, so the app loses the session on return.
 * Regular Safari and installed Android PWAs don't have this problem.
 */
export function isIosStandalonePwa(): boolean {
  return isIos() && isStandalone();
}

/**
 * iOS, in a browser that can add the app to the home screen (Safari, Chrome), not in the
 * installed app. iOS has no install prompt, so people must use the Share menu themselves.
 * In-app browsers (Facebook, Instagram, LINE) have no such menu item.
 */
export function canAddToIosHomeScreen(): boolean {
  return isIos() && !isStandalone() && !/FBAN|FBAV|Instagram|Line\//.test(navigator.userAgent);
}
