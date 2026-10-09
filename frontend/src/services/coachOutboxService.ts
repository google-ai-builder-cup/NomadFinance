import { requestBackgroundSync, saveEntry } from "@/lib/coachOutboxStore";
import { apiUrl } from "@/services/apiClient";
import { getIdToken } from "@/services/authService";
import type { CoachTurnRequest } from "@/types/coach";
import { createEntry } from "@/utils/coachOutbox";

/**
 * Keep an answer that could not be sent, and ask the browser to wake the service worker when the
 * connection is back. The token goes with it so the worker can send it with the app closed; it is
 * short-lived (an hour), and the entry is wiped when the answer goes through, when the interview
 * is restarted and on sign-out.
 */
export async function keepForLater(
  request: CoachTurnRequest,
  uid: string,
  turnCount: number
): Promise<void> {
  let token: string | null = null;
  try {
    token = await getIdToken();
  } catch {
    // Offline with a token that has lapsed: the screen sends it itself when it can.
  }
  await saveEntry(
    createEntry({
      request,
      uid,
      turnCount,
      url: apiUrl(`/api/v2/coach/sessions/${encodeURIComponent(request.sessionId)}/messages`),
      token,
      now: Date.now(),
    })
  );
  void requestBackgroundSync();
}
