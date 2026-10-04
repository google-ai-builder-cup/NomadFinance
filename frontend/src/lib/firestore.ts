import { connectFirestoreEmulator, getFirestore } from "firebase/firestore";

import { firebaseApp } from "@/lib/firebase";

// Its own module (not in lib/firebase.ts) so a page that never reads data, like the landing
// and sign-in pages, does not download the Firestore SDK (NF-P4-003).
export const db = getFirestore(firebaseApp);

if (import.meta.env.VITE_USE_FIREBASE_EMULATOR === "true") {
  // Port 8085, not Firestore's default 8080, which the backend uses (frontend/firebase.json).
  connectFirestoreEmulator(
    db,
    "127.0.0.1",
    Number(import.meta.env.VITE_FIRESTORE_EMULATOR_PORT ?? 8085)
  );
}
