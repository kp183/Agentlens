"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  useAuth as useClerkAuth, 
  useUser as useClerkUser, 
  UserButton as ClerkUserButton,
  SignedIn as ClerkSignedIn,
  SignedOut as ClerkSignedOut,
  SignIn as ClerkSignIn,
  SignUp as ClerkSignUp
} from "@clerk/nextjs";

const isLocalMode = process.env.NEXT_PUBLIC_LOCAL_MODE === "true" || !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

// Global state for mock auth
interface MockUser {
  id: string;
  fullName: string;
  primaryEmailAddress: { emailAddress: string };
  emailAddresses: { emailAddress: string }[];
  imageUrl?: string;
}

interface MockAuthState {
  isSignedIn: boolean;
  userId: string | null;
  user: MockUser | null;
}

let mockAuthState: MockAuthState = {
  isSignedIn: true,
  userId: "user_mock_dev_100",
  user: {
    id: "user_mock_dev_100",
    fullName: "Agent Engineer",
    primaryEmailAddress: { emailAddress: "engineer@agentlens.local" },
    emailAddresses: [
      { emailAddress: "engineer@agentlens.local" }
    ],
    imageUrl: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&h=100&fit=crop&crop=faces"
  }
};

const listeners = new Set<() => void>();

function getMockState() {
  if (!mockAuthState.isSignedIn) {
    return {
      isSignedIn: false,
      userId: null,
      user: null
    };
  }
  return mockAuthState;
}

if (typeof window !== "undefined") {
  const stored = localStorage.getItem("agentlens_mock_auth");
  if (stored) {
    try {
      mockAuthState = { ...mockAuthState, ...JSON.parse(stored) };
    } catch (e) {}
  }
}

function updateMockState(state: Partial<typeof mockAuthState>) {
  mockAuthState = { ...mockAuthState, ...state };
  if (typeof window !== "undefined") {
    localStorage.setItem("agentlens_mock_auth", JSON.stringify(mockAuthState));
  }
  listeners.forEach(l => l());
}

// Hook 1: Mock useAuth
function useMockAuth() {
  const router = useRouter();
  const [state, setState] = useState(getMockState());

  useEffect(() => {
    const onChange = () => setState(getMockState());
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  return {
    isLoaded: true,
    isSignedIn: state.isSignedIn,
    userId: state.userId,
    orgId: "org_mock_dev_100",
    orgRole: "admin",
    orgSlug: "mock-org",
    getToken: async () => "mock_token_key_dev",
    signOut: async () => {
      updateMockState({ isSignedIn: false, userId: null });
      router.push("/");
    }
  };
}

// Hook 2: Mock useUser
function useMockUser() {
  const [state, setState] = useState(getMockState());

  useEffect(() => {
    const onChange = () => setState(getMockState());
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  return {
    isLoaded: true,
    isSignedIn: state.isSignedIn,
    user: state.user
  };
}

// Component 1: Mock SignedIn
function MockSignedIn({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState(getMockState());

  useEffect(() => {
    const onChange = () => setState(getMockState());
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  if (!state.isSignedIn) return null;
  return <>{children}</>;
}

// Component 2: Mock SignedOut
function MockSignedOut({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState(getMockState());

  useEffect(() => {
    const onChange = () => setState(getMockState());
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  if (state.isSignedIn) return null;
  return <>{children}</>;
}

// Component 3: Mock UserButton
function MockUserButton({ afterSignOutUrl = "/" }: { afterSignOutUrl?: string }) {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const [state, setState] = useState(getMockState());
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onChange = () => setState(getMockState());
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      setOpenUpward(spaceBelow < 200);
    }
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!state.isSignedIn || !state.user) return null;

  const handleSignOut = () => {
    updateMockState({ isSignedIn: false, userId: null });
    setIsOpen(false);
    router.push(afterSignOutUrl);
  };

  const initials = state.user.fullName
    ? state.user.fullName.split(" ").map(n => n[0]).join("")
    : "AE";

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-500/10 border border-indigo-500/30 text-xs font-semibold text-indigo-400 focus:outline-none hover:bg-indigo-500/20 transition-all duration-150 overflow-hidden"
      >
        {state.user.imageUrl ? (
          <img src={state.user.imageUrl} alt={state.user.fullName} className="h-full w-full object-cover" />
        ) : (
          <span>{initials}</span>
        )}
      </button>

      {isOpen && (
        <div className={`absolute right-0 w-56 origin-bottom-right rounded-xl border border-slate-800 bg-slate-900 p-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none z-50 animate-fadeIn ${
          openUpward ? "bottom-full mb-2" : "top-full mt-2"
        }`}>
          <div className="px-3 py-2 border-b border-slate-800 mb-1.5 text-left">
            <p className="text-xs font-semibold text-slate-200">{state.user.fullName}</p>
            <p className="text-[10px] text-slate-500 truncate">{state.user.emailAddresses[0]?.emailAddress}</p>
          </div>
          <button
            onClick={handleSignOut}
            className="w-full text-left flex items-center space-x-2 px-3 py-2 text-xs font-medium text-red-400 hover:bg-red-500/10 rounded-lg transition"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span>Sign Out</span>
          </button>
        </div>
      )}
    </div>
  );
}

// Component 4: Mock SignIn
function MockSignIn(props: any) {
  const router = useRouter();
  const handleMockLogin = (e: React.FormEvent) => {
    e.preventDefault();
    updateMockState({ isSignedIn: true, userId: "user_mock_dev_100" });
    router.push("/");
  };

  return (
    <div className="w-full max-w-[400px] p-6 space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold text-slate-100">Sign in to AgentLens</h1>
        <p className="text-sm text-slate-450">Local development mock login</p>
      </div>
      <form onSubmit={handleMockLogin} className="space-y-4">
        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Email Address</label>
          <input
            type="email"
            defaultValue="engineer@agentlens.local"
            className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
            required
            readOnly
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Password</label>
          <input
            type="password"
            defaultValue="••••••••"
            className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
            required
            readOnly
          />
        </div>
        <button
          type="submit"
          className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-lg shadow-indigo-600/10 transition"
        >
          Access Local Console
        </button>
      </form>
    </div>
  );
}

// Component 5: Mock SignUp
function MockSignUp(props: any) {
  const router = useRouter();
  const handleMockRegister = (e: React.FormEvent) => {
    e.preventDefault();
    updateMockState({ isSignedIn: true, userId: "user_mock_dev_100" });
    router.push("/");
  };

  return (
    <div className="w-full max-w-[400px] p-6 space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold text-slate-100">Create your account</h1>
        <p className="text-sm text-slate-450">Local development mock registration</p>
      </div>
      <form onSubmit={handleMockRegister} className="space-y-4">
        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Full Name</label>
          <input
            type="text"
            defaultValue="Agent Engineer"
            className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
            required
            readOnly
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Email Address</label>
          <input
            type="email"
            defaultValue="engineer@agentlens.local"
            className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
            required
            readOnly
          />
        </div>
        <button
          type="submit"
          className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-lg shadow-indigo-600/10 transition"
        >
          Register & Continue
        </button>
      </form>
    </div>
  );
}

// Conditional Exports
export const useAuth = isLocalMode ? useMockAuth : useClerkAuth;
export const useUser = isLocalMode ? useMockUser : useClerkUser;
export const UserButton = isLocalMode ? MockUserButton : ClerkUserButton;
export const SignedIn = isLocalMode ? MockSignedIn : ClerkSignedIn;
export const SignedOut = isLocalMode ? MockSignedOut : ClerkSignedOut;
export const SignIn = isLocalMode ? MockSignIn : ClerkSignIn;
export const SignUp = isLocalMode ? MockSignUp : ClerkSignUp;
