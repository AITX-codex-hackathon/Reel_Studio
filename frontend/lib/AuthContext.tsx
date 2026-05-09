"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { LoginDialog } from "@/components/auth/LoginDialog";
import { auth } from "@/lib/firebase";
import { onAuthStateChanged, signOut, User as FirebaseUser } from "firebase/auth";

interface User {
  id: string;
  name: string;
  email: string;
  isGuest?: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (user: User) => void;
  logout: () => void;
  requireAuth: (action: () => void) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      if (firebaseUser) {
        setUser({
          id: firebaseUser.uid,
          name: firebaseUser.displayName || firebaseUser.email?.split("@")[0] || "User",
          email: firebaseUser.email || "",
          isGuest: firebaseUser.isAnonymous,
        });
      } else {
        // We only reset user if they are completely logged out.
        // We might want to keep our mock "Guest" if it's not a real firebase anonymous auth yet.
        setUser(null);
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const login = (userData: User) => {
    setUser(userData);
    setIsLoginOpen(false);
    if (pendingAction) {
      pendingAction();
      setPendingAction(null);
    }
  };

  const logout = async () => {
    await signOut(auth);
    setUser(null);
  };

  const requireAuth = (action: () => void) => {
    if (user) {
      action();
    } else {
      setPendingAction(() => action);
      setIsLoginOpen(true);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, requireAuth }}>
      {children}
      <LoginDialog 
        open={isLoginOpen} 
        onOpenChange={(open) => {
          setIsLoginOpen(open);
          if (!open) setPendingAction(null);
        }} 
      />
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
