"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/AuthContext";
import { Sparkles } from "lucide-react";
import { auth, googleProvider, isFirebaseConfigured } from "@/lib/firebase";
import { 
  signInWithPopup, 
  signInWithEmailAndPassword, 
  createUserWithEmailAndPassword, 
  signInAnonymously 
} from "firebase/auth";

interface LoginDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LoginDialog({ open, onOpenChange }: LoginDialogProps) {
  const { login } = useAuth();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const FIREBASE_NOT_CONFIGURED =
    "Firebase isn't configured. Add NEXT_PUBLIC_FIREBASE_* keys to frontend/.env.local to enable sign-in.";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!auth) {
      setError(FIREBASE_NOT_CONFIGURED);
      return;
    }
    setIsLoading(true);
    try {
      if (isSignUp) {
        const userCred = await createUserWithEmailAndPassword(auth, email, password);
        login({ id: userCred.user.uid, name: email.split("@")[0], email });
      } else {
        const userCred = await signInWithEmailAndPassword(auth, email, password);
        login({ id: userCred.user.uid, name: email.split("@")[0], email });
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    if (!auth || !googleProvider) {
      setError(FIREBASE_NOT_CONFIGURED);
      return;
    }
    setIsLoading(true);
    try {
      const userCred = await signInWithPopup(auth, googleProvider);
      login({
        id: userCred.user.uid,
        name: userCred.user.displayName || "Google User",
        email: userCred.user.email || "",
      });
    } catch (err: any) {
      setError(err.message || "Google sign-in failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGuestSignIn = async () => {
    setError(null);
    if (!auth) {
      setError(FIREBASE_NOT_CONFIGURED);
      return;
    }
    setIsLoading(true);
    try {
      const userCred = await signInAnonymously(auth);
      login({ id: userCred.user.uid, name: "Guest User", email: "", isGuest: true });
    } catch (err: any) {
      setError(err.message || "Guest sign-in failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md border-border/40 bg-surface/95 backdrop-blur-xl">
        <DialogHeader className="space-y-3">
          <div className="w-10 h-10 mx-auto rounded-xl bg-gradient-brand flex items-center justify-center shadow-brand-soft mb-2">
            <Sparkles className="w-5 h-5 text-white" strokeWidth={2.5} />
          </div>
          <DialogTitle className="text-2xl text-center font-display font-bold">
            {isSignUp ? "Create an account" : "Welcome back"}
          </DialogTitle>
          <DialogDescription className="text-center text-ink-muted">
            {isSignUp 
              ? "Sign up to start creating beautiful AI reels." 
              : "Log in to your account to continue."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <Button 
            type="button" 
            variant="outline" 
            className="w-full relative bg-surface hover:bg-primary-50 hover:text-primary border-border transition-colors h-11"
            onClick={handleGoogleSignIn}
            disabled={isLoading}
          >
            <svg className="w-5 h-5 absolute left-4" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-surface px-2 text-ink-subtle">Or continue with email</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="text-sm text-red-500 text-center bg-red-50 p-2 rounded-md">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Input 
                type="email" 
                placeholder="Email address" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-11 bg-surface-alt border-border focus-visible:ring-primary-400"
              />
            </div>
            <div className="space-y-2">
              <Input 
                type="password" 
                placeholder="Password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-11 bg-surface-alt border-border focus-visible:ring-primary-400"
              />
            </div>
            <Button type="submit" disabled={isLoading} className="w-full bg-gradient-brand hover:shadow-brand-soft h-11 text-base font-medium">
              {isSignUp ? "Sign up" : "Log in"}
            </Button>
          </form>
        </div>

        <div className="text-center text-sm text-ink-muted mt-2">
          {isSignUp ? "Already have an account? " : "Don't have an account? "}
          <button 
            type="button" 
            onClick={() => setIsSignUp(!isSignUp)}
            className="text-primary-600 hover:text-primary-700 font-medium hover:underline transition-all"
          >
            {isSignUp ? "Log in" : "Sign up"}
          </button>
        </div>
        
        <div className="pt-4 border-t border-border/60 mt-4 text-center">
          <button 
            type="button" 
            onClick={handleGuestSignIn}
            disabled={isLoading}
            className="text-sm font-medium text-ink-muted hover:text-ink transition-colors underline underline-offset-4 disabled:opacity-50"
          >
            Continue as Guest
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
