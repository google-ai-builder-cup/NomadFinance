import { onAuthStateChanged, type User } from "firebase/auth";
import {
  createContext,
  createElement,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";

import { auth } from "@/lib/firebase";

export interface AuthState {
  user: User | null;
  /** True until Firebase has restored (or ruled out) a saved session on page load. */
  loading: boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export interface AuthProviderProps {
  children: ReactNode;
}

/** Tracks the signed-in Firebase user for the whole app. Wrap the router in it once. */
export default function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true });

  useEffect(() => onAuthStateChanged(auth, (user) => setState({ user, loading: false })), []);

  return createElement(AuthContext.Provider, { value: state }, children);
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (state === null) {
    throw new Error("useAuth() must be used inside <AuthProvider>.");
  }
  return state;
}
