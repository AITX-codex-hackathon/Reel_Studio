"use client";

import { useAuth } from "@/lib/AuthContext";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { User, LogOut, RefreshCcw } from "lucide-react";

export function UserNav() {
  const { user, loading, logout, requireAuth } = useAuth();

  if (loading) {
    return <div className="w-8 h-8 rounded-full bg-surface-alt animate-pulse ml-2" />;
  }

  if (!user) {
    return (
      <Button 
        variant="ghost" 
        size="sm" 
        onClick={() => requireAuth(() => {})}
        className="text-ink-muted hover:text-ink hover:bg-primary-50 ml-2"
      >
        Log in
      </Button>
    );
  }

  const handleSwitchAccount = async () => {
    await logout();
    // Open the login modal by requiring auth for a no-op action
    requireAuth(() => {});
  };

  const initials = user.name ? user.name.slice(0, 2).toUpperCase() : "U";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center justify-center w-8 h-8 rounded-full bg-gradient-soft text-primary-700 font-medium text-xs border border-border/60 hover:shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 ml-2">
          {user.isGuest ? <User className="w-4 h-4" /> : initials}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56 mt-1 border-border/40 bg-surface/95 backdrop-blur-xl shadow-card" align="end" forceMount>
        <DropdownMenuLabel className="font-normal py-3">
          <div className="flex flex-col space-y-1.5">
            <p className="text-sm font-medium leading-none text-ink">{user.name}</p>
            <p className="text-xs leading-none text-ink-muted">
              {user.email || (user.isGuest ? "Guest Session" : "")}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleSwitchAccount} className="cursor-pointer py-2.5">
          <RefreshCcw className="mr-2 h-4 w-4 text-ink-subtle" />
          <span>Switch account</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={logout} className="cursor-pointer py-2.5 text-accent-600 focus:text-accent-700 focus:bg-accent-50">
          <LogOut className="mr-2 h-4 w-4" />
          <span>Sign out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
