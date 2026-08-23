import { useEffect, useState } from "react";
import { onAuthStateChanged, signInWithPopup, signOut, User } from "firebase/auth";
import { auth, googleProvider } from "./firebase";

export function useAuthUser() {
  const [user, setUser] = useState<User | null | undefined>(undefined); // undefined = loading
  useEffect(() => onAuthStateChanged(auth, setUser), []);
  return user;
}

export function SignInScreen() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="rounded-lg border border-aegis-border bg-aegis-panel p-8 text-center">
        <h1 className="mb-2 text-xl font-semibold">AEGIS Ops Console</h1>
        <p className="mb-6 text-sm text-slate-400">
          Internal tool -- sign in with your ops Google account to view live cases.
        </p>
        <button
          onClick={() => signInWithPopup(auth, googleProvider)}
          className="rounded bg-aegis-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
        >
          Sign in with Google
        </button>
      </div>
    </div>
  );
}

export function SignOutButton() {
  return (
    <button
      onClick={() => signOut(auth)}
      className="text-xs text-slate-400 hover:text-slate-200 underline"
    >
      Sign out
    </button>
  );
}
